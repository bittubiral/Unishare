"""
auth.py - Authentication helpers: hashing, verification, session management
Includes university email validation for JUST university format:
  Students : 220120.cse@student.just.edu.bd
  Teachers : rahman.cse@teacher.just.edu.bd  (or @just.edu.bd)
"""

import re
import bcrypt
import streamlit as st
from modules.database import get_user_by_email, create_user, get_departments


# ── EMAIL RULES ───────────────────────────────────────────────────────────────

UNIVERSITY_DOMAIN = "just.edu.bd"
UNIVERSITY_FULL_NAME = "Jashore University of Science and Technology"

# Student email pattern: 6-digit ID . dept @ student.just.edu.bd
STUDENT_EMAIL_PATTERN = re.compile(
    r'^\d{6}\.[a-z]+@student\.just\.edu\.bd$', re.IGNORECASE
)

# Year-Semester mapping: label shown to user → numeric semester stored in DB
SEMESTER_OPTIONS = {
    "1st Year 1st Semester": 1,
    "1st Year 2nd Semester": 2,
    "2nd Year 1st Semester": 3,
    "2nd Year 2nd Semester": 4,
    "3rd Year 1st Semester": 5,
    "3rd Year 2nd Semester": 6,
    "4th Year 1st Semester": 7,
    "4th Year 2nd Semester": 8,
}

# Teacher email pattern: name.dept@teacher.just.edu.bd OR name@just.edu.bd
# Must NOT start with digits (that would be a student ID format)
TEACHER_EMAIL_PATTERN = re.compile(
    r'^[a-z][a-z0-9._]+@(teacher\.just\.edu\.bd|just\.edu\.bd)$', re.IGNORECASE
)


def validate_university_email(email: str, role: str) -> tuple[bool, str]:
    """
    Check that email matches the university format for the given role.

    Student  → 220120.cse@student.just.edu.bd
    Teacher  → rahman.cse@teacher.just.edu.bd  OR  name@just.edu.bd
    Admin    → any @just.edu.bd (created manually, not through signup)
    """
    email = email.strip().lower()

    if not email.endswith(UNIVERSITY_DOMAIN):
        return False, (
            f"❌ Only **{UNIVERSITY_DOMAIN}** email addresses are accepted.\n\n"
            f"Example formats:\n"
            f"- Student: `220120.cse@student.just.edu.bd`\n"
            f"- Teacher: `rahman.cse@teacher.just.edu.bd`"
        )

    if role == "student":
        if not STUDENT_EMAIL_PATTERN.match(email):
            return False, (
                "❌ Invalid student email format.\n\n"
                "Expected format: `220120.cse@student.just.edu.bd`\n"
                "_(6-digit StudentID.Department@student.just.edu.bd)_"
            )

    elif role == "teacher":
        if not TEACHER_EMAIL_PATTERN.match(email):
            return False, (
                "❌ Invalid teacher email format.\n\n"
                "Expected format: `rahman.cse@teacher.just.edu.bd`\n"
                "_(name.department@teacher.just.edu.bd)_"
            )

    return True, "✅ Valid university email."


def extract_dept_from_email(email: str) -> str:
    """
    Try to extract department code from email.
    e.g. 220120.cse@student.just.edu.bd → CSE
    """
    try:
        local = email.split("@")[0]        # 220120.cse
        parts = local.split(".")
        if len(parts) >= 2:
            return parts[-1].upper()       # CSE
    except Exception:
        pass
    return ""


# ── PASSWORD HELPERS ──────────────────────────────────────────────────────────

def semester_to_label(semester: int) -> str:
    """Convert numeric semester (1-8) back to 'Year-Semester' display label."""
    reverse_map = {v: k for k, v in SEMESTER_OPTIONS.items()}
    return reverse_map.get(semester, f"Semester {semester}" if semester else "—")


def hash_password(plain: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext against stored bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── AUTH LOGIC ────────────────────────────────────────────────────────────────

def login_user(email: str, password: str):
    """Attempt login; return (success, message, user_dict)."""
    user = get_user_by_email(email.strip().lower())
    if not user:
        return False, "No account found with that email.", None
    if not user["is_active"]:
        return False, "Your account has been deactivated. Contact admin.", None
    if not verify_password(password, user["password_hash"]):
        return False, "Incorrect password.", None
    return True, "Welcome back!", user


def logout():
    """Clear session state."""
    for key in ["user", "logged_in"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def is_authenticated() -> bool:
    return st.session_state.get("logged_in", False)


def current_user() -> dict | None:
    return st.session_state.get("user", None)


def require_auth():
    """Stop rendering and show login prompt if not authenticated."""
    if not is_authenticated():
        st.warning("🔒 Please log in to access this page.")
        st.stop()


def require_role(*roles):
    """Stop rendering if user doesn't have one of the given roles."""
    require_auth()
    user = current_user()
    if user["role"] not in roles:
        st.error("⛔ You don't have permission to access this page.")
        st.stop()


# ── LOGIN / SIGNUP UI ─────────────────────────────────────────────────────────

def render_login_page():
    """Render combined login / signup form."""
    st.markdown("""
    <style>
    .auth-header{font-family:'Georgia',serif;font-size:2rem;font-weight:700;
                 color:#1a1a2e;text-align:center;margin-bottom:0.2rem}
    .auth-sub{text-align:center;color:#6b7280;margin-bottom:1.5rem;font-size:0.95rem}
    .email-hint{background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;
                padding:0.6rem 1rem;font-size:0.82rem;color:#0369a1;margin-bottom:0.5rem}
    </style>
    <div class="auth-header">📚 UniShare Platform</div>
    <div class="auth-sub">{UNIVERSITY_FULL_NAME}</div>
    """.replace("{UNIVERSITY_FULL_NAME}", UNIVERSITY_FULL_NAME), unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["🔑 Login", "📝 Sign Up"])

    # ── LOGIN ──
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("University Email",
                                  placeholder="220120.cse@student.just.edu.bd")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", use_container_width=True)

        if submitted:
            ok, msg, user = login_user(email, password)
            if ok:
                st.session_state["logged_in"] = True
                st.session_state["user"] = user
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    # ── SIGN UP ──
    with tab_signup:

        # Email format hint box
        st.markdown("""
        <div class="email-hint">
            🎓 <b>Only official JUST university emails are accepted</b><br>
            &nbsp;&nbsp;• Student &nbsp;→ <code>220120.cse@student.just.edu.bd</code><br>
            &nbsp;&nbsp;• Teacher &nbsp;→ <code>rahman.cse@teacher.just.edu.bd</code>
        </div>
        """, unsafe_allow_html=True)

        departments = get_departments()
        dept_map = {d["name"]: d["id"] for d in departments}

        # Role selector OUTSIDE the form so the page reruns immediately
        # when switched — this lets us show/hide Semester & Student ID live.
        role = st.selectbox("Role *", ["student", "teacher"], key="signup_role")

        with st.form("signup_form"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("Full Name *")
                email_s = st.text_input(
                    "University Email *",
                    placeholder="220120.cse@student.just.edu.bd",
                    key="signup_email"
                )
                password_s = st.text_input("Password *", type="password", key="signup_pw")
                confirm_pw = st.text_input("Confirm Password *", type="password")

            with col2:
                dept_name = st.selectbox("Department *", list(dept_map.keys()))
                semester = None
                student_id = None
                if role == "student":
                    year_sem_label = st.selectbox(
                        "Current Semester *", list(SEMESTER_OPTIONS.keys())
                    )
                    semester = SEMESTER_OPTIONS[year_sem_label]
                    student_id = st.text_input(
                        "Student ID *",
                        placeholder="e.g. 220120",
                        max_chars=6,
                        help="Exactly 6 digits — same number used in your email"
                    )
                # Teachers don't see Semester or Student ID at all

            submitted_s = st.form_submit_button("Create Account", use_container_width=True)

        if submitted_s:
            # Basic field checks
            if not name or not email_s or not password_s:
                st.error("All fields marked * are required.")
            elif password_s != confirm_pw:
                st.error("Passwords do not match.")
            elif len(password_s) < 6:
                st.error("Password must be at least 6 characters.")
            elif role == "student" and (not student_id or not student_id.isdigit() or len(student_id) != 6):
                st.error("❌ Student ID must be exactly **6 digits** (e.g. 220120).")
            else:
                # ── UNIVERSITY EMAIL VALIDATION ──
                email_ok, email_msg = validate_university_email(email_s.strip(), role)
                if not email_ok:
                    st.error(email_msg)
                else:
                    # Auto-detect department from email and block if mismatch
                    detected_dept = extract_dept_from_email(email_s)
                    selected_dept_code = next(
                        (d["code"] for d in departments if d["name"] == dept_name), ""
                    )
                    if detected_dept and detected_dept != selected_dept_code.upper():
                        st.error(
                            f"❌ Department mismatch! Your email suggests **{detected_dept}** "
                            f"but you selected **{selected_dept_code}**. "
                            f"Please select the correct department matching your email."
                        )
                    else:
                        pw_hash = hash_password(password_s)
                        ok, msg = create_user(
                            name, email_s.strip().lower(), pw_hash, role,
                            dept_map[dept_name], semester, student_id
                        )
                        if ok:
                            st.success(f"✅ Account created! Please log in.")
                            st.info(
                                "🔒 Your university email has been verified. "
                                "Welcome to UniShare!"
                            )
                        else:
                            st.error(msg)