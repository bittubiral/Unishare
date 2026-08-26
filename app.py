"""
app.py - Main entry point for the Department Resource Sharing Platform
Run with: streamlit run app.py
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="UniShare — Department Resource Platform",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

from modules.database import init_db
init_db()

from modules.database import get_connection
from modules.auth import hash_password

def seed_demo():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if count > 0:
        return
    from modules.database import create_user, add_course, get_departments
    depts = get_departments()
    cse_id = next((d["id"] for d in depts if d["code"] == "CSE"), depts[0]["id"])
    create_user("Admin User", "admin@uni.edu", hash_password("admin123"), "admin", cse_id)
    create_user("Dr. Rahman", "teacher@uni.edu", hash_password("teacher123"), "teacher", cse_id)
    create_user("Arif Hossain", "student@uni.edu", hash_password("student123"), "student", cse_id, semester=5, student_id="CSE2001")
    add_course("CSE301", "Operating Systems", 5, cse_id)
    add_course("CSE302", "Database Management", 5, cse_id)
    add_course("CSE401", "Artificial Intelligence", 7, cse_id)
    add_course("CSE201", "Data Structures", 3, cse_id)
    add_course("CSE101", "Intro to Programming", 1, cse_id)

seed_demo()

from modules.auth import is_authenticated, render_login_page
from modules.ui_components import inject_css, render_sidebar
from modules.pages import (
    page_dashboard, page_browse, page_upload,
    page_favorites, page_my_uploads, page_analytics, page_admin
)
from modules.teacher_rating import page_rate_teacher, page_my_ratings
from modules.appointments import page_appointments_student, page_appointments_teacher
from modules.penalty_system import page_my_profile, page_issue_violation

inject_css()

if not is_authenticated():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        render_login_page()
else:
    user = st.session_state["user"]

    # Check suspension on every load
    from modules.database import get_user_penalty_status, bd_now
    penalty = get_user_penalty_status(user["id"])
    if penalty:
        suspended_until = penalty.get("suspended_until")
        if suspended_until and bd_now().strftime("%Y-%m-%d") <= suspended_until:
            st.error(f"🚫 Your account is suspended until **{suspended_until}**")
            st.warning(f"Reason: {penalty.get('suspension_reason','Violation of platform rules')}")
            st.info("You may submit an appeal from your profile page.")
            if st.button("📋 Go to My Profile to Appeal"):
                st.session_state["force_page"] = "👤 My Profile"
                st.rerun()
            st.stop()

    selected = st.session_state.pop("force_page", None) or render_sidebar(user)

    if selected == "🏠 Dashboard":
        page_dashboard(user)
    elif selected == "🔍 Browse Resources":
        page_browse(user)
    elif selected == "📤 Upload Resource":
        page_upload(user)
    elif selected == "⭐ My Favorites":
        page_favorites(user)
    elif selected == "👤 My Uploads":
        page_my_uploads(user)
    elif selected == "📊 Analytics":
        page_analytics(user)
    elif selected == "⭐ Rate My Teacher":
        page_rate_teacher(user)
    elif selected == "📈 My Ratings":
        page_my_ratings(user)
    elif selected == "📅 Appointments":
        if user["role"] == "student":
            page_appointments_student(user)
        elif user["role"] == "teacher":
            page_appointments_teacher(user)
    elif selected == "👤 My Profile":
        page_my_profile(user)
    elif selected == "⚠️ Issue Violation":
        page_issue_violation(user)
    elif selected == "🛡️ Admin Panel":
        from modules.auth import require_role
        require_role("admin")
        page_admin(user)