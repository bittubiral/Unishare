"""
file_manager.py - Handles file upload, storage, validation, and download
"""

import os
import hashlib
import streamlit as st
from datetime import datetime
from modules.database import (add_resource, get_resource_by_id,
                               increment_download, get_courses, bd_now)

# Allowed file types and their MIME types
ALLOWED_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ppt": "application/vnd.ms-powerpoint",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}

MAX_FILE_SIZE_MB = 50
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

CATEGORIES = {
    "lecture_note": "📖 Lecture Note",
    "assignment": "📝 Assignment",
    "lab_report": "🔬 Lab Report",
    "presentation": "🖥️ Presentation",
    "past_paper": "📄 Past Paper",
    "book": "📚 Book / Reference",
    "other": "📎 Other",
}


EVIDENCE_ALLOWED_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}
EVIDENCE_MAX_FILES = 3
EVIDENCE_MAX_SIZE_MB = 10
EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evidence")


def validate_evidence_file(uploaded_file) -> tuple[bool, str]:
    """Return (is_valid, error_message) for a single evidence image."""
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
    if ext not in EVIDENCE_ALLOWED_TYPES:
        return False, f"'.{ext}' isn't a supported image type. Use PNG or JPG."
    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > EVIDENCE_MAX_SIZE_MB:
        return False, f"Image too large ({size_mb:.1f} MB). Max: {EVIDENCE_MAX_SIZE_MB} MB."
    return True, ""


def save_evidence_files(uploaded_files, owner_id: int) -> tuple[list[str], list[str]]:
    """
    Validate and save up to EVIDENCE_MAX_FILES evidence images to disk.
    Returns (stored_relative_paths, errors). Relative paths are stored in the
    DB (comma-joined) and resolved back to disk with evidence_file_path().
    """
    errors = []
    stored = []
    if not uploaded_files:
        return stored, errors

    if len(uploaded_files) > EVIDENCE_MAX_FILES:
        errors.append(f"You can attach at most {EVIDENCE_MAX_FILES} images — "
                      f"only the first {EVIDENCE_MAX_FILES} were saved.")
        uploaded_files = uploaded_files[:EVIDENCE_MAX_FILES]

    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    user_dir = os.path.join(EVIDENCE_DIR, str(owner_id))
    os.makedirs(user_dir, exist_ok=True)

    for f in uploaded_files:
        valid, err = validate_evidence_file(f)
        if not valid:
            errors.append(f"{f.name}: {err}")
            continue
        timestamp = bd_now().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = f.name.replace(" ", "_")
        stored_name = f"{timestamp}_{safe_name}"
        with open(os.path.join(user_dir, stored_name), "wb") as out:
            out.write(f.getbuffer())
        stored.append(f"{owner_id}/{stored_name}")

    return stored, errors


def evidence_file_path(relative_path: str) -> str:
    """Resolve a stored relative evidence path back to an absolute disk path."""
    return os.path.join(EVIDENCE_DIR, relative_path)


def render_evidence_thumbnails(evidence_files_str: str, caption: str = "Evidence"):
    """Render stored evidence images (comma-joined relative paths) inline."""
    if not evidence_files_str:
        return
    paths = [p.strip() for p in evidence_files_str.split(",") if p.strip()]
    if not paths:
        return
    cols = st.columns(len(paths))
    for col, rel_path in zip(cols, paths):
        abs_path = evidence_file_path(rel_path)
        with col:
            if os.path.exists(abs_path):
                st.image(abs_path, caption=caption, use_container_width=True)
            else:
                st.caption("⚠️ Evidence image missing on server.")


def ensure_upload_dir():
    """Create uploads directory if missing."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_file_hash(data: bytes) -> str:
    """Compute SHA-256 hash of file bytes for duplicate detection."""
    return hashlib.sha256(data).hexdigest()


def save_uploaded_file(uploaded_file, uploader_id: int) -> tuple[str, str]:
    """
    Save an uploaded file to disk under uploads/<uploader_id>/<timestamp>_<filename>.
    Returns (file_path, stored_file_name).
    """
    ensure_upload_dir()
    user_dir = os.path.join(UPLOAD_DIR, str(uploader_id))
    os.makedirs(user_dir, exist_ok=True)

    timestamp = bd_now().strftime("%Y%m%d_%H%M%S")
    safe_name = uploaded_file.name.replace(" ", "_")
    stored_name = f"{timestamp}_{safe_name}"
    file_path = os.path.join(user_dir, stored_name)

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path, stored_name


def validate_file(uploaded_file) -> tuple[bool, str]:
    """Return (is_valid, error_message)."""
    if uploaded_file is None:
        return False, "No file selected."

    ext = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
    if ext not in ALLOWED_TYPES:
        return False, f"File type '.{ext}' not allowed. Allowed: {', '.join(ALLOWED_TYPES.keys())}"

    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return False, f"File too large ({size_mb:.1f} MB). Max: {MAX_FILE_SIZE_MB} MB."

    return True, ""


def render_upload_form(user: dict):
    """Render the resource upload form."""
    st.subheader("📤 Upload New Resource")

    courses = get_courses()
    if not courses:
        st.warning("No courses available. Ask an admin to add courses first.")
        return

    course_options = {f"{c['code']} — {c['name']}": c["id"] for c in courses}

    with st.form("upload_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Resource Title *", placeholder="e.g. Operating Systems Week 3 Notes")
            description = st.text_area("Description", placeholder="Brief description of the resource...", height=100)
            tags = st.text_input("Tags (comma-separated)", placeholder="e.g. OS, processes, scheduling")

        with col2:
            course_label = st.selectbox("Course *", list(course_options.keys()))
            category_key = st.selectbox("Category *", list(CATEGORIES.keys()),
                                        format_func=lambda k: CATEGORIES[k])
            from modules.auth import SEMESTER_OPTIONS
            year_sem_label = st.selectbox("Semester *", list(SEMESTER_OPTIONS.keys()))
            semester = SEMESTER_OPTIONS[year_sem_label]
            uploaded_file = st.file_uploader(
                "Choose File *",
                type=list(ALLOWED_TYPES.keys()),
                help=f"Max {MAX_FILE_SIZE_MB}MB. Allowed: {', '.join(ALLOWED_TYPES.keys())}"
            )

        submit = st.form_submit_button("🚀 Upload Resource", use_container_width=True)

    if submit:
        if not title:
            st.error("Please enter a title.")
            return
        if not uploaded_file:
            st.error("Please select a file.")
            return

        valid, err = validate_file(uploaded_file)
        if not valid:
            st.error(err)
            return

        file_path, stored_name = save_uploaded_file(uploaded_file, user["id"])
        ext = uploaded_file.name.rsplit(".", 1)[-1].lower()

        add_resource(
            title=title,
            description=description,
            file_name=stored_name,
            file_path=file_path,
            file_type=ext,
            file_size=uploaded_file.size,
            category=category_key,
            course_id=course_options[course_label],
            semester=semester,
            uploader_id=user["id"],
            tags=tags
        )

        if user["role"] in ("teacher", "admin"):
            st.success("✅ Resource uploaded and published!")
        else:
            st.success("✅ Resource uploaded! Awaiting admin approval before it appears publicly.")


def render_download_button(resource: dict, user: dict):
    """Render a download button for a resource."""
    file_path = resource.get("file_path", "")
    if not os.path.exists(file_path):
        st.caption("⚠️ File not found on server.")
        return

    with open(file_path, "rb") as f:
        data = f.read()

    ext = resource.get("file_type", "bin")
    mime = ALLOWED_TYPES.get(ext, "application/octet-stream")
    file_name = resource.get("file_name", f"resource.{ext}")

    if st.download_button(
        label="⬇️ Download",
        data=data,
        file_name=file_name,
        mime=mime,
        key=f"dl_{resource['id']}_{user['id']}",
        use_container_width=True
    ):
        increment_download(resource["id"], user["id"])


def format_file_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    else:
        return f"{size_bytes/(1024*1024):.1f} MB"


def get_file_icon(file_type: str) -> str:
    """Return emoji icon for file type."""
    icons = {
        "pdf": "📄", "doc": "📝", "docx": "📝",
        "ppt": "🖥️", "pptx": "🖥️", "xlsx": "📊",
        "zip": "🗜️", "txt": "📃",
        "png": "🖼️", "jpg": "🖼️", "jpeg": "🖼️",
    }
    return icons.get(file_type.lower(), "📎")