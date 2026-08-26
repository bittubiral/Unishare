"""
pages.py - All page renderers for the platform
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from modules.database import (
    get_resources, get_stats, get_all_users, get_departments, get_courses,
    add_department, add_course, approve_resource, delete_resource,
    toggle_user_active, update_user_role, get_pending_resources,
    get_user_favorites
)
from modules.ui_components import render_resource_card, render_search_filters, metric_cards
from modules.file_manager import render_upload_form, CATEGORIES


# ── DASHBOARD ────────────────────────────────────────────────────────────────

def page_dashboard(user: dict):
    st.markdown("<div class='page-header'>🏠 Dashboard</div>", unsafe_allow_html=True)

    # Stats row
    stats = get_stats()
    metric_cards(stats)

    st.divider()

    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.markdown("#### 🕐 Recently Uploaded")
        recent = get_resources(approved_only=True, limit=6)
        if not recent:
            st.info("No resources uploaded yet. Be the first!")
        for r in recent:
            render_resource_card(r, user)

    with col_side:
        # Pending notice for admin/teacher
        if user["role"] in ("teacher", "admin"):
            pending = get_pending_resources()
            if pending:
                st.warning(f"⏳ {len(pending)} resource(s) awaiting approval")

        # Category breakdown chart
        st.markdown("#### 📊 Resources by Type")
        by_cat = stats.get("by_category", [])
        if by_cat:
            df_cat = pd.DataFrame([(CATEGORIES.get(r[0], r[0]), r[1]) for r in by_cat],
                                   columns=["Category", "Count"])
            fig = px.pie(df_cat, names="Category", values="Count",
                         color_discrete_sequence=px.colors.qualitative.Pastel,
                         hole=0.4)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=280,
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)


# ── BROWSE RESOURCES ─────────────────────────────────────────────────────────

def page_browse(user: dict):
    st.markdown("<div class='page-header'>🔍 Browse Resources</div>", unsafe_allow_html=True)

    filters = render_search_filters()
    st.divider()

    resources = get_resources(
        semester=filters["semester"],
        course_id=filters["course_id"],
        category=filters["category"],
        search_query=filters["query"],
        approved_only=True
    )

    # Sort
    if filters["sort"] == "Most Downloaded":
        resources.sort(key=lambda r: r.get("download_count", 0), reverse=True)
    elif filters["sort"] == "Top Rated":
        resources.sort(key=lambda r: r.get("avg_rating", 0) or 0, reverse=True)

    st.caption(f"Found **{len(resources)}** resource(s)")

    if not resources:
        st.info("No resources match your filters. Try broadening your search.")
        return

    for r in resources:
        render_resource_card(r, user)


# ── UPLOAD RESOURCE ───────────────────────────────────────────────────────────

def page_upload(user: dict):
    st.markdown("<div class='page-header'>📤 Upload Resource</div>", unsafe_allow_html=True)
    render_upload_form(user)


# ── MY FAVORITES ─────────────────────────────────────────────────────────────

def page_favorites(user: dict):
    st.markdown("<div class='page-header'>⭐ My Favorites</div>", unsafe_allow_html=True)
    favs = get_user_favorites(user["id"])
    if not favs:
        st.info("You haven't saved any resources yet. Browse and click 🤍 Save on any resource.")
        return
    for r in favs:
        render_resource_card(r, user)


# ── MY UPLOADS ───────────────────────────────────────────────────────────────

def page_my_uploads(user: dict):
    st.markdown("<div class='page-header'>👤 My Uploads</div>", unsafe_allow_html=True)
    uploads = get_resources(uploader_id=user["id"], approved_only=False)
    if not uploads:
        st.info("You haven't uploaded anything yet.")
        return

    for r in uploads:
        col1, col2 = st.columns([5, 1])
        with col1:
            render_resource_card(r, user, show_actions=(r["is_approved"] == 1))
        with col2:
            if r["is_approved"] == 0:
                st.markdown("<span class='badge badge-pending'>Pending</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='badge badge-approved'>Published</span>", unsafe_allow_html=True)
            if user["role"] == "admin" or r["uploader_id"] == user["id"]:
                if st.button("🗑️ Delete", key=f"del_{r['id']}"):
                    delete_resource(r["id"])
                    st.success("Resource deleted.")
                    st.rerun()


# ── ANALYTICS ────────────────────────────────────────────────────────────────

def page_analytics(user: dict):
    st.markdown("<div class='page-header'>📊 Analytics Dashboard</div>", unsafe_allow_html=True)

    stats = get_stats()
    metric_cards(stats)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🏆 Top Downloaded Resources")
        top = stats.get("top_resources", [])
        if top:
            df_top = pd.DataFrame([(r[0], r[1], r[2]) for r in top],
                                   columns=["Title", "Downloads", "Course"])
            st.dataframe(df_top, use_container_width=True, hide_index=True)
        else:
            st.caption("No data yet.")

    with col2:
        st.markdown("#### 💾 Storage Usage")
        storage_mb = stats.get("storage_mb", 0)
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=storage_mb,
            title={"text": "Storage Used (MB)"},
            gauge={"axis": {"range": [0, 1000]},
                   "bar": {"color": "#2c5f8a"},
                   "steps": [{"range": [0, 500], "color": "#e0f2fe"},
                              {"range": [500, 1000], "color": "#fed7aa"}]}
        ))
        fig3.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=30, b=10, l=10, r=10))
        st.plotly_chart(fig3, use_container_width=True)


# ── ADMIN PANEL ───────────────────────────────────────────────────────────────

def page_admin(user: dict):
    st.markdown("<div class='page-header'>🛡️ Admin Panel</div>", unsafe_allow_html=True)

    tab_users, tab_pending, tab_courses, tab_depts, tab_teacher_ratings, tab_appointments, tab_penalties, tab_comment_reports, tab_rating_reports = st.tabs([
        "👥 Users", "⏳ Pending Approval", "📚 Courses", "🏫 Departments",
        "⭐ Teacher Ratings", "📅 Appointments", "⚠️ Penalties", "💬 Comment Reports", "🚩 Reported Reviews"
    ])

    # ── USERS ──
    with tab_users:
        st.markdown("#### Manage Users")
        users = get_all_users()
        if not users:
            st.info("No users yet.")
        else:
            df = pd.DataFrame(users)[["id", "name", "email", "role", "dept_name",
                                       "semester", "is_active", "created_at"]]
            df.columns = ["ID", "Name", "Email", "Role", "Department",
                          "Semester", "Active", "Joined"]
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("#### Modify User")
            uid = st.number_input("User ID", min_value=1, step=1)
            col1, col2, col3 = st.columns(3)
            with col1:
                new_role = st.selectbox("Set Role", ["student", "teacher", "admin"])
                if st.button("Update Role"):
                    update_user_role(uid, new_role)
                    st.success("Role updated.")
                    st.rerun()
            with col2:
                if st.button("✅ Activate User"):
                    toggle_user_active(uid, 1)
                    st.success("User activated.")
                    st.rerun()
            with col3:
                if st.button("🚫 Deactivate User"):
                    toggle_user_active(uid, 0)
                    st.warning("User deactivated.")
                    st.rerun()

    # ── PENDING RESOURCES ──
    with tab_pending:
        st.markdown("#### Resources Awaiting Approval")
        pending = get_pending_resources()
        if not pending:
            st.success("🎉 No pending resources!")
        else:
            for r in pending:
                with st.container():
                    col1, col2, col3 = st.columns([4, 1, 1])
                    with col1:
                        st.markdown(f"**{r['title']}** — _{r.get('course_code', '—')}_ "
                                    f"· {r.get('uploader_name', '?')} · "
                                    f"{r.get('file_type', '').upper()}")
                        if r.get("description"):
                            st.caption(r["description"][:100])
                    with col2:
                        if st.button("✅ Approve", key=f"appr_{r['id']}"):
                            approve_resource(r["id"])
                            st.success("Approved!")
                            st.rerun()
                    with col3:
                        if st.button("🗑️ Delete", key=f"del_pend_{r['id']}"):
                            delete_resource(r["id"])
                            st.warning("Deleted.")
                            st.rerun()
                    st.divider()

    # ── COURSES ──
    with tab_courses:
        st.markdown("#### All Courses")
        courses = get_courses()
        if courses:
            df_c = pd.DataFrame(courses)[["id", "code", "name", "semester", "dept_name", "teacher_name"]]
            df_c.columns = ["ID", "Code", "Name", "Semester", "Department", "Teacher"]
            st.dataframe(df_c, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### Add New Course")
        departments = get_departments()
        dept_map = {d["name"]: d["id"] for d in departments}
        with st.form("add_course_form"):
            cc1, cc2 = st.columns(2)
            with cc1:
                c_code = st.text_input("Course Code *", placeholder="e.g. CSE301")
                c_name = st.text_input("Course Name *", placeholder="e.g. Operating Systems")
            with cc2:
                c_sem = st.number_input("Semester", 1, 8, 1)
                c_dept = st.selectbox("Department", list(dept_map.keys()))
            submitted = st.form_submit_button("Add Course", use_container_width=True)
        if submitted:
            ok, msg = add_course(c_code, c_name, c_sem, dept_map[c_dept])
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    # ── DEPARTMENTS ──
    with tab_depts:
        st.markdown("#### All Departments")
        depts = get_departments()
        df_d = pd.DataFrame(depts)
        st.dataframe(df_d, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### Add Department")
        with st.form("add_dept_form"):
            d_name = st.text_input("Department Name *")
            d_code = st.text_input("Department Code *", placeholder="e.g. CSE")
            submitted_d = st.form_submit_button("Add Department")
        if submitted_d:
            if add_department(d_name, d_code):
                st.success("Department added.")
                st.rerun()
            else:
                st.error("Department name or code already exists.")

    # ── TEACHER RATINGS ──
    with tab_teacher_ratings:
        from modules.teacher_rating import page_admin_teacher_ratings
        page_admin_teacher_ratings()

    # ── APPOINTMENTS ──
    with tab_appointments:
        from modules.appointments import page_appointments_admin
        page_appointments_admin()

    # ── PENALTIES ──
    with tab_penalties:
        from modules.penalty_system import page_admin_penalties
        page_admin_penalties()

    # ── COMMENT REPORTS ──
    with tab_comment_reports:
        from modules.database import get_comment_reports, update_comment_report_status, VIOLATION_TYPES
        st.markdown("#### 💬 Reported Comments")
        
        pending_reports = get_comment_reports("pending")
        all_reports = get_comment_reports()
        
        st.caption(f"{len(pending_reports)} pending report(s) out of {len(all_reports)} total")
        
        if not all_reports:
            st.info("No comment reports yet.")
        else:
            for report in all_reports:
                status_icon = {"pending": "⏳", "actioned": "✅",
                               "dismissed": "❌", "reviewed": "👁️"}.get(report["status"], "❓")
                
                with st.expander(f"{status_icon} {report['reporter_name']} reported "
                                f"**{report['comment_author_name']}** ({report['comment_author_role']}) "
                                f"· {report['created_at'][:10]}"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**Reported comment:** _{report['comment_text']}_")
                        st.markdown(f"**Reason:** {report['reason']}")
                        st.markdown(f"Status: **{report['status'].title()}**")
                    with col2:
                        st.write(f"Reporter: {report['reporter_name']}")
                        st.write(f"Author: {report['comment_author_name']}")
                    
                    if report["status"] == "pending":
                        st.markdown("**Take action:**")
                        v_type = st.selectbox(
                            "Violation type",
                            list(VIOLATION_TYPES.keys()),
                            format_func=lambda k: VIOLATION_TYPES[k][0],
                            key=f"vtype_cmt_{report['id']}"
                        )
                        also_delete = st.checkbox(
                            "Also delete this comment",
                            key=f"cmt_also_del_{report['id']}"
                        )
                        col_a, col_b, col_c, col_d = st.columns(4)
                        with col_a:
                            if st.button("⚠️ Issue Violation", key=f"cmt_viol_{report['id']}",
                                         use_container_width=True):
                                from modules.database import issue_violation, delete_comment
                                ok, msg = issue_violation(
                                    report["comment_author_id"],
                                    st.session_state["user"]["id"],
                                    v_type,
                                    f"Reported comment: \"{report['comment_text']}\" — "
                                    f"Reason: {report['reason']}",
                                    comment_id=report["comment_id"]
                                )
                                if also_delete:
                                    delete_comment(report["comment_id"])
                                    msg += " Comment deleted."
                                update_comment_report_status(report["id"], "actioned",
                                                            st.session_state["user"]["id"])
                                st.success(msg)
                                st.rerun()
                        with col_b:
                            if st.button("🗑️ Delete Comment", key=f"cmt_del_{report['id']}",
                                         use_container_width=True):
                                st.session_state[f"confirm_del_cmt_{report['id']}"] = True
                        with col_c:
                            if st.button("👁️ Mark Reviewed", key=f"cmt_rev_{report['id']}",
                                         use_container_width=True):
                                update_comment_report_status(report["id"], "reviewed",
                                                            st.session_state["user"]["id"])
                                st.rerun()
                        with col_d:
                            if st.button("❌ Dismiss", key=f"cmt_dis_{report['id']}",
                                         use_container_width=True):
                                update_comment_report_status(report["id"], "dismissed",
                                                            st.session_state["user"]["id"])
                                st.rerun()

                        if st.session_state.get(f"confirm_del_cmt_{report['id']}"):
                            st.warning("⚠️ This permanently deletes the comment. This can't be undone.")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Confirm Delete", key=f"cmt_del_confirm_{report['id']}",
                                             use_container_width=True):
                                    from modules.database import delete_comment
                                    delete_comment(report["comment_id"])
                                    update_comment_report_status(report["id"], "actioned",
                                                                st.session_state["user"]["id"])
                                    st.session_state.pop(f"confirm_del_cmt_{report['id']}", None)
                                    st.success("Comment deleted.")
                                    st.rerun()
                            with c2:
                                if st.button("Cancel", key=f"cmt_del_cancel_{report['id']}",
                                             use_container_width=True):
                                    st.session_state.pop(f"confirm_del_cmt_{report['id']}", None)
                                    st.rerun()

    # ── REPORTED REVIEWS (Teacher Ratings) ──
    with tab_rating_reports:
        from modules.database import (
            get_rating_reports, update_rating_report_status, issue_violation, VIOLATION_TYPES
        )
        st.markdown("#### 🚩 Reported Student Reviews")
        st.caption("Teachers flag anonymous reviews they believe are inappropriate. "
                   "Only admin can see the student's identity here.")

        pending_rr = get_rating_reports("pending")
        all_rr = get_rating_reports()

        st.caption(f"{len(pending_rr)} pending report(s) out of {len(all_rr)} total")

        if not all_rr:
            st.info("No reported reviews yet.")
        else:
            for rr in all_rr:
                status_icon = {"pending": "⏳", "actioned": "✅",
                               "dismissed": "❌", "reviewed": "👁️"}.get(rr["status"], "❓")

                with st.expander(f"{status_icon} {rr['teacher_name']} reported a review "
                                 f"· {rr['course_code']} · {rr['created_at'][:10]}"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**Reported review:** _{rr['review']}_")
                        st.markdown(f"**Report reason:** {rr['reason']}")
                        st.markdown(f"**Scores:** Teaching {rr['teaching_quality']}/5 · "
                                    f"Communication {rr['communication']}/5 · "
                                    f"Material {rr['course_material']}/5")
                    with col2:
                        st.write(f"**Student:** {rr['student_name']} (visible to admin only)")
                        st.write(f"**Teacher:** {rr['teacher_name']}")
                        st.write(f"**Reported by:** {rr['reporter_name']}")
                        st.write(f"Status: **{rr['status'].title()}**")

                    if rr["status"] == "pending":
                        st.markdown("**Take action:**")
                        v_type = st.selectbox(
                            "Violation type",
                            list(VIOLATION_TYPES.keys()),
                            format_func=lambda k: VIOLATION_TYPES[k][0],
                            key=f"vtype_rr_{rr['id']}"
                        )
                        also_delete_rr = st.checkbox(
                            "Also delete this review's text",
                            key=f"rr_also_del_{rr['id']}"
                        )
                        col_a, col_b, col_c, col_d = st.columns(4)
                        with col_a:
                            if st.button("⚠️ Issue Violation", key=f"rr_viol_{rr['id']}",
                                         use_container_width=True):
                                from modules.database import delete_review_text
                                ok, msg = issue_violation(
                                    rr["student_id"],
                                    st.session_state["user"]["id"],
                                    v_type,
                                    f"Reported review: \"{rr['review']}\" — Reason: {rr['reason']}"
                                )
                                if also_delete_rr:
                                    delete_review_text(rr["rating_id"])
                                    msg += " Review text deleted."
                                update_rating_report_status(rr["id"], "actioned",
                                                            st.session_state["user"]["id"])
                                st.success(msg)
                                st.rerun()
                        with col_b:
                            if st.button("🗑️ Delete Review", key=f"rr_del_{rr['id']}",
                                         use_container_width=True):
                                st.session_state[f"confirm_del_rr_{rr['id']}"] = True
                        with col_c:
                            if st.button("👁️ Mark Reviewed", key=f"rr_rev_{rr['id']}",
                                         use_container_width=True):
                                update_rating_report_status(rr["id"], "reviewed",
                                                            st.session_state["user"]["id"])
                                st.rerun()
                        with col_d:
                            if st.button("❌ Dismiss", key=f"rr_dis_{rr['id']}",
                                         use_container_width=True):
                                update_rating_report_status(rr["id"], "dismissed",
                                                            st.session_state["user"]["id"])
                                st.rerun()

                        if st.session_state.get(f"confirm_del_rr_{rr['id']}"):
                            st.warning("⚠️ This permanently deletes the written review text "
                                      "(the 1-5 star scores are kept). This can't be undone.")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅ Confirm Delete", key=f"rr_del_confirm_{rr['id']}",
                                             use_container_width=True):
                                    from modules.database import delete_review_text
                                    delete_review_text(rr["rating_id"])
                                    update_rating_report_status(rr["id"], "actioned",
                                                                st.session_state["user"]["id"])
                                    st.session_state.pop(f"confirm_del_rr_{rr['id']}", None)
                                    st.success("Review text deleted.")
                                    st.rerun()
                            with c2:
                                if st.button("Cancel", key=f"rr_del_cancel_{rr['id']}",
                                             use_container_width=True):
                                    st.session_state.pop(f"confirm_del_rr_{rr['id']}", None)
                                    st.rerun()