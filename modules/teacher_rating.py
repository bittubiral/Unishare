"""
teacher_rating.py - Rate My Teacher feature
- Students can rate teachers per course (anonymous)
- Teachers see only averages + anonymous reviews, can reply
- Admins see everything including student names
"""

import streamlit as st
from modules.database import (
    get_teachers, get_courses, submit_teacher_rating,
    get_student_existing_rating, get_teacher_rating_summary,
    get_teacher_reviews, get_teacher_reviews_admin,
    add_teacher_reply, get_all_teacher_ratings_admin
)


def _stars(score):
    """Convert numeric score to star emojis."""
    score = round(score or 0)
    return "⭐" * score + "☆" * (5 - score)


def _score_bar(label, score):
    """Render a labeled score row."""
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
        <span style="width:160px;font-size:0.9rem">{label}</span>
        <span style="font-size:1.1rem;color:#f59e0b">{_stars(score)}</span>
        <span style="font-weight:600">{score}/5</span>
    </div>
    """, unsafe_allow_html=True)


# ── STUDENT: SUBMIT RATING ────────────────────────────────────────────────────

def page_rate_teacher(user: dict):
    st.markdown("<div class='page-header'>⭐ Rate My Teacher</div>",
                unsafe_allow_html=True)

    if user["role"] != "student":
        st.warning("Only students can rate teachers.")
        return

    teachers = get_teachers()
    courses = get_courses()

    if not teachers:
        st.info("No teachers available to rate yet.")
        return
    if not courses:
        st.info("No courses available.")
        return

    teacher_map = {t["name"]: t["id"] for t in teachers}
    course_map = {f"{c['code']} — {c['name']}": c["id"] for c in courses}

    st.markdown("### 📋 Submit a Rating")
    st.caption("Your identity is kept **anonymous** — teachers cannot see your name.")

    col1, col2 = st.columns(2)
    with col1:
        teacher_name = st.selectbox("Select Teacher", list(teacher_map.keys()))
    with col2:
        course_label = st.selectbox("Select Course", list(course_map.keys()))

    teacher_id = teacher_map[teacher_name]
    course_id = course_map[course_label]

    # Check if already rated
    existing = get_student_existing_rating(teacher_id, user["id"], course_id)
    if existing:
        st.info(f"✏️ You already rated **{teacher_name}** for this course. "
                f"Submitting again will **update** your previous rating.")

    with st.form("teacher_rating_form"):
        st.markdown("#### Rate the following (1 = Poor, 5 = Excellent)")

        tq_default = existing["teaching_quality"] if existing else 3
        cm_default = existing["communication"] if existing else 3
        mat_default = existing["course_material"] if existing else 3

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            teaching_quality = st.slider(
                "🎓 Teaching Quality", 1, 5, tq_default,
                help="How clearly does the teacher explain concepts?"
            )
        with col_b:
            communication = st.slider(
                "💬 Communication", 1, 5, cm_default,
                help="How approachable and responsive is the teacher?"
            )
        with col_c:
            course_material = st.slider(
                "📚 Course Material", 1, 5, mat_default,
                help="How useful are the provided materials?"
            )

        review = st.text_area(
            "✍️ Written Review (optional)",
            value=existing["review"] if existing else "",
            placeholder="Share your experience with this teacher...",
            height=100
        )

        submitted = st.form_submit_button("🚀 Submit Rating", use_container_width=True)

    if submitted:
        ok, msg = submit_teacher_rating(
            teacher_id, user["id"], course_id,
            teaching_quality, communication, course_material, review
        )
        if ok:
            st.success(f"✅ {msg}")
            st.rerun()
        else:
            st.error(f"❌ {msg}")

    # Show summary of selected teacher
    st.divider()
    st.markdown(f"### 📊 {teacher_name}'s Overall Ratings")
    _render_teacher_summary(teacher_id)


# ── TEACHER: VIEW MY RATINGS ──────────────────────────────────────────────────

def page_my_ratings(user: dict):
    st.markdown("<div class='page-header'>📊 My Teaching Ratings</div>",
                unsafe_allow_html=True)

    if user["role"] != "teacher":
        st.warning("This page is for teachers only.")
        return

    # Summary cards
    summary = get_teacher_rating_summary(user["id"])
    total = summary.get("total_ratings") or 0

    if total == 0:
        st.info("No ratings received yet. Students will rate you after taking your courses.")
        return

    st.markdown(f"#### You have received **{total}** rating(s)")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎓 Teaching Quality",
                f"{summary.get('avg_teaching') or 0}/5",
                _stars(summary.get('avg_teaching') or 0))
    col2.metric("💬 Communication",
                f"{summary.get('avg_communication') or 0}/5",
                _stars(summary.get('avg_communication') or 0))
    col3.metric("📚 Course Material",
                f"{summary.get('avg_material') or 0}/5",
                _stars(summary.get('avg_material') or 0))
    col4.metric("⭐ Overall Average",
                f"{summary.get('overall_avg') or 0}/5",
                _stars(summary.get('overall_avg') or 0))

    st.divider()

    # Anonymous reviews + reply
    st.markdown("#### 💬 Student Reviews (Anonymous)")
    reviews = get_teacher_reviews(user["id"])

    if not reviews:
        st.caption("No written reviews yet.")
        return

    for rev in reviews:
        with st.container():
            st.markdown(f"""
            <div class="resource-card">
                <div class="muted">
                    📘 <b>{rev['course_code']}</b> — {rev['course_name']} ·
                    {rev['created_at'][:10]}
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                _score_bar("🎓 Teaching Quality", rev["teaching_quality"])
            with col_b:
                _score_bar("💬 Communication", rev["communication"])
            with col_c:
                _score_bar("📚 Course Material", rev["course_material"])

            if rev.get("review") is None:
                # review was explicitly wiped by an admin (delete_review_text)
                st.caption("🚫 This review's written comment was removed by a moderator. "
                          "The star ratings above are unaffected.")
            elif rev.get("review"):
                # normal case: student wrote something
                st.markdown(f"> 💬 *\"{rev['review']}\"*")

                # Report button — teacher can flag an inappropriate anonymous review
                col_r1, col_r2 = st.columns([5, 1])
                with col_r2:
                    if st.button("🚩 Report", key=f"report_rev_{rev['id']}",
                                 use_container_width=True):
                        st.session_state[f"reporting_rev_{rev['id']}"] = True

                if st.session_state.get(f"reporting_rev_{rev['id']}"):
                    from modules.database import report_teacher_rating
                    st.warning("🚩 Reporting this review as inappropriate")
                    reason = st.text_input(
                        "Reason for report *",
                        key=f"reason_rev_{rev['id']}",
                        placeholder="e.g. Offensive language, harassment, personal attack..."
                    )
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        if st.button("✅ Submit Report", key=f"submit_rev_{rev['id']}",
                                     use_container_width=True):
                            if reason.strip():
                                ok, msg = report_teacher_rating(rev["id"], user["id"], reason.strip())
                                if ok:
                                    st.success(msg)
                                    st.session_state.pop(f"reporting_rev_{rev['id']}", None)
                                    st.rerun()
                                else:
                                    st.error(msg)
                            else:
                                st.warning("Please provide a reason.")
                    with col_s2:
                        if st.button("Cancel", key=f"cancel_rev_{rev['id']}",
                                     use_container_width=True):
                            st.session_state.pop(f"reporting_rev_{rev['id']}", None)
                            st.rerun()
            # else: review == "" — student just didn't write anything; show nothing

            # Show existing reply or reply form
            if rev.get("teacher_reply"):
                st.success(f"**Your Reply** ({rev['reply_date'][:10]}): {rev['teacher_reply']}")
                if st.button("✏️ Edit Reply", key=f"edit_reply_{rev['id']}"):
                    st.session_state[f"editing_reply_{rev['id']}"] = True
                    st.rerun()

            if not rev.get("teacher_reply") or st.session_state.get(f"editing_reply_{rev['id']}"):
                with st.form(f"reply_form_{rev['id']}"):
                    reply_text = st.text_area(
                        "Your Reply",
                        value=rev.get("teacher_reply") or "",
                        placeholder="Write a response to this review...",
                        height=80
                    )
                    if st.form_submit_button("💬 Post Reply", use_container_width=True):
                        if reply_text.strip():
                            add_teacher_reply(rev["id"], user["id"], reply_text.strip())
                            st.session_state.pop(f"editing_reply_{rev['id']}", None)
                            st.success("Reply posted!")
                            st.rerun()
                        else:
                            st.warning("Reply cannot be empty.")

            st.divider()


# ── ADMIN: SEE ALL TEACHER RATINGS ───────────────────────────────────────────

def page_admin_teacher_ratings():
    st.markdown("#### 🛡️ All Teacher Ratings (Admin View)")
    st.caption("Admin can see student names — teachers cannot.")

    teachers = get_teachers()
    if not teachers:
        st.info("No teachers yet.")
        return

    teacher_map = {"All Teachers": None}
    teacher_map.update({t["name"]: t["id"] for t in teachers})
    selected = st.selectbox("Filter by Teacher", list(teacher_map.keys()))
    teacher_id = teacher_map[selected]

    if teacher_id:
        # Summary for selected teacher
        _render_teacher_summary(teacher_id)
        st.divider()
        reviews = get_teacher_reviews_admin(teacher_id)
        st.markdown(f"#### Reviews for {selected}")
        if not reviews:
            st.info("No reviews yet.")
        for rev in reviews:
            with st.expander(f"👤 {rev['student_name']} ({rev.get('student_roll','')}) — "
                             f"{rev['course_code']} · {rev['created_at'][:10]}"):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    _score_bar("🎓 Teaching", rev["teaching_quality"])
                with col_b:
                    _score_bar("💬 Communication", rev["communication"])
                with col_c:
                    _score_bar("📚 Material", rev["course_material"])
                if rev.get("review") is None:
                    st.caption("🚫 Review text removed by a moderator.")
                elif rev.get("review"):
                    st.markdown(f"> *\"{rev['review']}\"*")
                else:
                    st.caption("_No written comment left._")
                if rev.get("teacher_reply"):
                    st.info(f"**Teacher Reply:** {rev['teacher_reply']}")
    else:
        # Show all ratings as table
        all_ratings = get_all_teacher_ratings_admin()
        if not all_ratings:
            st.info("No ratings submitted yet.")
        else:
            import pandas as pd
            df = pd.DataFrame(all_ratings)[[
                "teacher_name", "student_name", "course_code",
                "teaching_quality", "communication", "course_material", "created_at"
            ]]
            df.columns = ["Teacher", "Student", "Course",
                          "Teaching", "Communication", "Material", "Date"]
            st.dataframe(df, use_container_width=True, hide_index=True)


# ── SHARED: TEACHER SUMMARY WIDGET ───────────────────────────────────────────

def _render_teacher_summary(teacher_id):
    """Show average rating summary for a teacher (no student names)."""
    summary = get_teacher_rating_summary(teacher_id)
    total = summary.get("total_ratings") or 0

    if total == 0:
        st.caption("No ratings yet for this teacher.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎓 Teaching", f"{summary.get('avg_teaching') or 0}/5")
    col2.metric("💬 Communication", f"{summary.get('avg_communication') or 0}/5")
    col3.metric("📚 Material", f"{summary.get('avg_material') or 0}/5")
    col4.metric("⭐ Overall", f"{summary.get('overall_avg') or 0}/5")
    st.caption(f"Based on {total} rating(s)")