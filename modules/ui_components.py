"""
ui_components.py - Reusable UI components: cards, resource table, search bar, sidebar
"""

import streamlit as st
import pandas as pd
from modules.database import (
    get_resources, get_courses, is_favorited, toggle_favorite,
    upsert_rating, get_user_rating, get_comments, add_comment, delete_comment
)
from modules.file_manager import render_download_button, format_file_size, get_file_icon, CATEGORIES


# ── THEME CSS ─────────────────────────────────────────────────────────────────

LIGHT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Source+Sans+3:wght@400;500;600&display=swap');

:root {
    --bg: #f7f6f2;
    --card-bg: #ffffff;
    --accent: #2c5f8a;
    --accent2: #e8612a;
    --text: #1a1a2e;
    --muted: #6b7280;
    --border: #e2e0d8;
    --success: #1a7f4b;
    --shadow: 0 2px 12px rgba(0,0,0,0.08);
}

html, body, [class*="css"] {
    font-family: 'Source Sans 3', sans-serif !important;
    background-color: var(--bg) !important;
}

h1,h2,h3 { font-family: 'Merriweather', serif !important; }

.resource-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: var(--shadow);
    transition: box-shadow 0.2s;
}
.resource-card:hover { box-shadow: 0 4px 20px rgba(44,95,138,0.15); }

.metric-card {
    background: var(--card-bg);
    border-left: 4px solid var(--accent);
    border-radius: 8px;
    padding: 1rem 1.2rem;
    box-shadow: var(--shadow);
}

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 4px;
}
.badge-student { background:#dbeafe; color:#1e40af; }
.badge-teacher { background:#dcfce7; color:#166534; }
.badge-admin   { background:#fef3c7; color:#92400e; }
.badge-pending { background:#fee2e2; color:#991b1b; }
.badge-approved{ background:#d1fae5; color:#065f46; }

.page-header {
    font-family: 'Merriweather', serif;
    font-size: 1.7rem;
    font-weight: 700;
    color: var(--text);
    border-bottom: 2px solid var(--accent);
    padding-bottom: 0.4rem;
    margin-bottom: 1.2rem;
}

.star-rating { font-size: 1rem; color: #f59e0b; }
.muted { color: var(--muted); font-size: 0.85rem; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #1a1a2e !important;
}
section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}
</style>
"""

DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Source+Sans+3:wght@400;500;600&display=swap');

:root {
    --bg: #0f172a;
    --card-bg: #1e293b;
    --accent: #38bdf8;
    --accent2: #fb923c;
    --text: #f1f5f9;
    --muted: #94a3b8;
    --border: #334155;
    --success: #34d399;
    --shadow: 0 2px 12px rgba(0,0,0,0.4);
}

html, body, [class*="css"] {
    font-family: 'Source Sans 3', sans-serif !important;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}

h1,h2,h3 { font-family: 'Merriweather', serif !important; color: var(--text) !important; }

.resource-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: var(--shadow);
}

.metric-card {
    background: var(--card-bg);
    border-left: 4px solid var(--accent);
    border-radius: 8px;
    padding: 1rem 1.2rem;
    box-shadow: var(--shadow);
}

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 4px;
}
.badge-student { background:#1e3a5f; color:#93c5fd; }
.badge-teacher { background:#14532d; color:#86efac; }
.badge-admin   { background:#451a03; color:#fcd34d; }
.badge-pending { background:#450a0a; color:#fca5a5; }
.badge-approved{ background:#022c22; color:#6ee7b7; }

.page-header {
    font-family: 'Merriweather', serif;
    font-size: 1.7rem;
    font-weight: 700;
    color: var(--text);
    border-bottom: 2px solid var(--accent);
    padding-bottom: 0.4rem;
    margin-bottom: 1.2rem;
}

.star-rating { font-size: 1rem; color: #fbbf24; }
.muted { color: var(--muted); font-size: 0.85rem; }

section[data-testid="stSidebar"] {
    background: #0f172a !important;
}
section[data-testid="stSidebar"] * {
    color: #cbd5e1 !important;
}
</style>
"""


def inject_css():
    dark = st.session_state.get("dark_mode", False)
    st.markdown(DARK_CSS if dark else LIGHT_CSS, unsafe_allow_html=True)


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

def render_sidebar(user: dict):
    """Render sidebar navigation based on user role."""
    with st.sidebar:
        st.markdown(f"### 📚 UniShare")
        st.markdown(f"**{user['name']}**")
        role_badge = f"<span class='badge badge-{user['role']}'>{user['role'].title()}</span>"
        st.markdown(role_badge, unsafe_allow_html=True)
        st.divider()

        pages = ["🏠 Dashboard", "🔍 Browse Resources", "📤 Upload Resource", "⭐ My Favorites"]

        # Role-specific pages
        if user["role"] == "student":
            pages.append("⭐ Rate My Teacher")
            pages.append("📅 Appointments")
            pages.append("👤 My Profile")
        if user["role"] == "teacher":
            pages.append("📈 My Ratings")
            pages.append("📅 Appointments")
            pages.append("⚠️ Issue Violation")
        if user["role"] in ("teacher", "admin"):
            pages.append("📊 Analytics")
        if user["role"] == "admin":
            pages.append("🛡️ Admin Panel")

        pages.append("👤 My Uploads")

        selected = st.radio("Navigation", pages, label_visibility="collapsed")

        st.divider()
        # Notification bell
        from modules.appointments import render_notification_panel
        render_notification_panel(user)
        st.divider()
        dark = st.toggle("🌙 Dark Mode", value=st.session_state.get("dark_mode", False))
        if dark != st.session_state.get("dark_mode", False):
            st.session_state["dark_mode"] = dark
            st.rerun()

        if st.button("🚪 Logout", use_container_width=True):
            from modules.auth import logout
            logout()

    return selected


# ── METRIC CARDS ──────────────────────────────────────────────────────────────

def metric_cards(stats: dict):
    cols = st.columns(4)
    items = [
        ("📁 Resources", stats.get("total_resources", 0), "published"),
        ("👥 Users", stats.get("total_users", 0), "registered"),
        ("⬇️ Downloads", stats.get("total_downloads", 0), "total"),
        ("📚 Courses", stats.get("total_courses", 0), "active"),
    ]
    for col, (label, value, sub) in zip(cols, items):
        with col:
            st.metric(label, value, sub)


# ── RESOURCE CARD ─────────────────────────────────────────────────────────────

def render_resource_card(resource: dict, user: dict, show_actions=True):
    """Render a single resource card with metadata, rating, favorite, download."""
    icon = get_file_icon(resource.get("file_type", ""))
    cat_label = CATEGORIES.get(resource.get("category", "other"), "Other")
    avg_rating = resource.get("avg_rating", 0) or 0
    stars = "★" * int(round(avg_rating)) + "☆" * (5 - int(round(avg_rating)))

    with st.container():
        desc_snippet = resource.get('description', '') or ''
        description_html = ""
        if resource.get('description'):
            snippet = desc_snippet[:120] + ("..." if len(desc_snippet) > 120 else "")
            description_html = f"<p style='margin-top:0.5rem;color:var(--muted)'>{snippet}</p>"

        # Tags: stored as a comma-separated string, render as pill badges.
        raw_tags = resource.get('tags', '') or ''
        tag_list = [t.strip() for t in raw_tags.split(',') if t.strip()]
        tags_html = ""
        if tag_list:
            pills = "".join(
                f'<span style="display:inline-block;background:var(--bg);'
                f'border:1px solid var(--border);color:var(--muted);'
                f'border-radius:12px;padding:1px 10px;font-size:0.78rem;'
                f'margin:0.4rem 6px 0 0">#{t}</span>'
                for t in tag_list
            )
            tags_html = f'<div style="margin-top:0.3rem">{pills}</div>'

        card_html = (
            '<div class="resource-card">'
            '<div style="display:flex;justify-content:space-between;align-items:flex-start">'
            '<div style="flex:1">'
            '<div style="display:flex;align-items:center;gap:0.4rem">'
            f'<span style="font-size:1.3rem;line-height:1">{icon}</span>'
            f'<span style="font-size:1.1rem;font-weight:700;color:var(--text)">{resource["title"]}</span>'
            '</div>'
            '<div class="muted">'
            f'{resource.get("course_code","—")} · {resource.get("course_name","")} · '
            f'Semester {resource.get("semester","")} · {cat_label}'
            '</div>'
            '<div class="muted">'
            f'Uploaded by <b>{resource.get("uploader_name","?")}</b> · '
            f'{format_file_size(resource.get("file_size",0))} · '
            f'{resource.get("file_type","").upper()} · '
            f'⬇️ {resource.get("download_count",0)}'
            '</div>'
            f'{tags_html}'
            '</div>'
            '<div style="text-align:right;white-space:nowrap">'
            f'<div class="star-rating">{stars}</div>'
            f'<div class="muted">{avg_rating:.1f} ({resource.get("rating_count",0)} ratings)</div>'
            '</div>'
            '</div>'
            f'{description_html}'
            '</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

    if show_actions:
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            render_download_button(resource, user)
        with col2:
            fav = is_favorited(resource["id"], user["id"])
            fav_label = "💛 Saved" if fav else "🤍 Save"
            if st.button(fav_label, key=f"fav_{resource['id']}_{user['id']}",
                         use_container_width=True):
                toggle_favorite(resource["id"], user["id"])
                st.rerun()
        with col3:
            my_rating = get_user_rating(resource["id"], user["id"]) or 0
            star_options = {
                0: "Rate ☆☆☆☆☆",
                1: "★☆☆☆☆ (1)",
                2: "★★☆☆☆ (2)",
                3: "★★★☆☆ (3)",
                4: "★★★★☆ (4)",
                5: "★★★★★ (5)",
            }
            options_list = [0, 1, 2, 3, 4, 5] if my_rating == 0 else [1, 2, 3, 4, 5]
            new_rating = st.selectbox(
                "Rate this resource",
                options_list,
                index=options_list.index(my_rating) if my_rating in options_list else 0,
                format_func=lambda x: star_options[x],
                key=f"rate_{resource['id']}_{user['id']}",
                label_visibility="collapsed",
                help="Click to rate this resource 1-5 stars"
            )
            if new_rating != my_rating and new_rating != 0:
                upsert_rating(resource["id"], user["id"], new_rating)
                st.rerun()
        with col4:
            comment_count = len(get_comments(resource["id"]))
            with st.expander(f"💬 Comments ({comment_count})"):
                _render_comments(resource, user)


def _render_comments(resource: dict, user: dict):
    """Comment section with reporting capability for teachers and students."""
    from modules.database import report_comment
    comments = get_comments(resource["id"])

    if not comments:
        st.caption("No comments yet.")

    for c in comments:
        role_b = f"<span class='badge badge-{c['user_role']}'>{c['user_role']}</span>"
        st.markdown(f"**{c['user_name']}** {role_b} · <span class='muted'>{c['created_at'][:10]}</span>",
                    unsafe_allow_html=True)
        st.write(c["content"])

        col1, col2 = st.columns([1, 1])
        with col1:
            if user["role"] == "admin" or c["user_id"] == user["id"]:
                if st.button("🗑️ Delete", key=f"del_cmt_{c['id']}",
                             use_container_width=True):
                    delete_comment(c["id"])
                    st.rerun()
        with col2:
            # Both students and teachers can report comments (not their own)
            if user["role"] in ("student", "teacher") and c["user_id"] != user["id"]:
                if st.button("🚩 Report", key=f"report_cmt_{c['id']}",
                             use_container_width=True):
                    st.session_state[f"reporting_cmt_{c['id']}"] = True

        # Direct inline report form — appears right under the reported comment
        if st.session_state.get(f"reporting_cmt_{c['id']}"):
            st.warning("🚩 Reporting this comment")
            reason = st.text_input(
                "Reason for report *",
                key=f"reason_{c['id']}",
                placeholder="e.g. Offensive language, harassment, spam...",
            )
            col_submit, col_cancel = st.columns(2)
            with col_submit:
                if st.button("✅ Submit Report", key=f"submit_report_{c['id']}",
                             use_container_width=True):
                    if reason.strip():
                        ok, msg = report_comment(c["id"], user["id"], reason.strip())
                        if ok:
                            st.success(msg)
                            st.session_state.pop(f"reporting_cmt_{c['id']}", None)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Please provide a reason.")
            with col_cancel:
                if st.button("Cancel", key=f"cancel_report_{c['id']}",
                             use_container_width=True):
                    st.session_state.pop(f"reporting_cmt_{c['id']}", None)
                    st.rerun()

        st.divider()

    new_comment = st.text_input("Add comment", key=f"cmt_input_{resource['id']}",
                                 placeholder="Write something...")
    if st.button("Post", key=f"post_cmt_{resource['id']}"):
        if new_comment.strip():
            add_comment(resource["id"], user["id"], new_comment.strip())
            st.rerun()


# ── SEARCH & FILTER ───────────────────────────────────────────────────────────

def render_search_filters():
    """Render search bar + filter controls; return filter dict."""
    st.markdown("#### 🔍 Search & Filter")
    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])

    with col1:
        query = st.text_input("Search", placeholder="Title, course code, tags…",
                               label_visibility="collapsed")
    courses = get_courses()
    course_opts = {"All Courses": None}
    course_opts.update({f"{c['code']} — {c['name']}": c["id"] for c in courses})

    with col2:
        semester = st.selectbox("Semester", ["All"] + list(range(1, 9)),
                                 label_visibility="collapsed")
    with col3:
        course_label = st.selectbox("Course", list(course_opts.keys()),
                                     label_visibility="collapsed")
    with col4:
        cat_opts = {"All Types": None}
        cat_opts.update({v: k for k, v in CATEGORIES.items()})
        cat_label = st.selectbox("Category", list(cat_opts.keys()),
                                  label_visibility="collapsed")
    with col5:
        sort = st.selectbox("Sort", ["Newest", "Most Downloaded", "Top Rated"],
                             label_visibility="collapsed")

    return {
        "query": query or None,
        "semester": None if semester == "All" else semester,
        "course_id": course_opts[course_label],
        "category": cat_opts.get(cat_label),
        "sort": sort,
    }