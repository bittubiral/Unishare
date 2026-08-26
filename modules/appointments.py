"""
appointments.py - Teacher Appointment System with Cancel Poll
- Students book group appointments with teachers
- Any student in the group can start a cancel poll
- If >50% vote Yes → appointment auto-cancelled
- Notifications shown in sidebar badge
"""

import streamlit as st
from datetime import date, datetime, timedelta
from modules.database import (
    bd_now,
    get_teachers, get_courses, create_appointment, get_appointments_for_student,
    get_appointments_for_teacher, get_all_appointments, get_appointment_by_id,
    update_appointment_status, join_appointment, get_participants, is_participant,
    create_cancel_poll, get_cancel_poll, submit_poll_vote, get_student_vote,
    get_notifications, mark_notifications_read, get_unread_count
)


# ── STATUS STYLING ────────────────────────────────────────────────────────────

STATUS_STYLE = {
    "pending":   ("⏳", "#fef3c7", "#92400e"),
    "approved":  ("✅", "#d1fae5", "#065f46"),
    "rejected":  ("❌", "#fee2e2", "#991b1b"),
    "cancelled": ("🚫", "#f3f4f6", "#374151"),
    "completed": ("🎓", "#dbeafe", "#1e40af"),
}

URGENCY_STYLE = {
    "low":    ("🟢", "Low"),
    "normal": ("🟡", "Normal"),
    "high":   ("🔴", "High"),
}


def _status_badge(status):
    icon, bg, color = STATUS_STYLE.get(status, ("❓", "#fff", "#000"))
    return f"<span style='background:{bg};color:{color};padding:2px 10px;border-radius:20px;font-size:0.8rem;font-weight:600'>{icon} {status.title()}</span>"


def _urgency_badge(urgency):
    icon, label = URGENCY_STYLE.get(urgency, ("🟡", "Normal"))
    return f"{icon} {label}"


# ── NOTIFICATION BELL ─────────────────────────────────────────────────────────

def render_notification_panel(user: dict):
    """Show notification badge + dropdown in sidebar."""
    unread = get_unread_count(user["id"])
    label = f"🔔 Notifications {'🔴' if unread > 0 else ''}"

    with st.sidebar.expander(f"{label} ({unread} new)" if unread else label):
        notifications = get_notifications(user["id"])
        if not notifications:
            st.caption("No notifications yet.")
        else:
            for n in notifications:
                style = "font-weight:600" if not n["is_read"] else "color:gray"
                st.markdown(
                    f"<div style='{style};font-size:0.85rem;padding:4px 0'>"
                    f"{n['message']}<br>"
                    f"<span style='color:#9ca3af;font-size:0.75rem'>{n['created_at'][:16]}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                st.divider()
            if unread > 0:
                if st.button("✓ Mark all as read", use_container_width=True):
                    mark_notifications_read(user["id"])
                    st.rerun()


# ── STUDENT: BOOK APPOINTMENT ─────────────────────────────────────────────────

def _book_appointment_form(user: dict):
    st.markdown("### 📝 Book a New Appointment")
    st.caption("Fill in the details and other students can join your appointment.")

    teachers = get_teachers()
    courses = get_courses()

    if not teachers:
        st.warning("No teachers available.")
        return
    if not courses:
        st.warning("No courses available.")
        return

    teacher_map = {t["name"]: t["id"] for t in teachers}
    course_map = {"None": None}
    course_map.update({f"{c['code']} — {c['name']}": c["id"] for c in courses})

    with st.form("book_appointment_form"):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Appointment Title *",
                                  placeholder="e.g. Project Discussion, Exam Help")
            teacher_name = st.selectbox("Select Teacher *", list(teacher_map.keys()))
            course_label = st.selectbox("Related Course", list(course_map.keys()))
            from modules.auth import SEMESTER_OPTIONS
            year_sem_label = st.selectbox("Semester *", list(SEMESTER_OPTIONS.keys()))
            urgency = st.selectbox("Urgency", ["normal", "low", "high"],
                                   format_func=lambda x: _urgency_badge(x))

        with col2:
            proposed_date = st.date_input(
                "Preferred Date *",
                min_value=bd_now().date() + timedelta(days=1),
                value=bd_now().date() + timedelta(days=2)
            )
            proposed_time = st.time_input("Preferred Time *",
                                          value=datetime.strptime("10:00", "%H:%M").time())
            purpose = st.selectbox("Purpose *", [
                "Project Discussion", "Exam Preparation", "Assignment Help",
                "Research Guidance", "Career Advice", "Course Query", "Other"
            ])
            description = st.text_area("Additional Details",
                                       placeholder="Describe what you want to discuss...",
                                       height=80)

        submitted = st.form_submit_button("📅 Book Appointment", use_container_width=True)

    if submitted:
        if not title:
            st.error("Please enter a title.")
            return

        semester = SEMESTER_OPTIONS[year_sem_label]
        appt_id = create_appointment(
            title=title,
            description=f"[{year_sem_label}] {description}".strip(),
            teacher_id=teacher_map[teacher_name],
            course_id=course_map[course_label],
            proposed_date=str(proposed_date),
            proposed_time=str(proposed_time)[:5],
            purpose=purpose,
            urgency=urgency,
            created_by=user["id"]
        )
        st.success(f"✅ Appointment booked for **{year_sem_label}**! Other students can now join it.")
        st.rerun()


# ── CANCEL POLL WIDGET ────────────────────────────────────────────────────────

def _render_cancel_poll(appt: dict, user: dict):
    """Render cancel poll: start one or vote on existing."""
    appt_id = appt["id"]
    poll = get_cancel_poll(appt_id)

    if appt["status"] != "pending" and appt["status"] != "approved":
        return  # Only poll active appointments

    st.markdown("---")

    if not poll:
        # No poll yet — any participant can start one
        if is_participant(appt_id, user["id"]) or appt.get("created_by") == user["id"]:
            with st.expander("🗳️ Start a Cancel Poll"):
                with st.form(f"start_poll_{appt_id}"):
                    reason = st.text_area("Why do you want to cancel?",
                                          placeholder="e.g. Scheduling conflict, rescheduling needed...",
                                          height=80)
                    if st.form_submit_button("Start Poll", use_container_width=True):
                        if reason.strip():
                            ok, msg = create_cancel_poll(appt_id, user["id"], reason.strip())
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("Please provide a reason.")
    else:
        # Poll exists — show vote status
        total_participants = len(get_participants(appt_id))
        yes_votes = poll.get("yes_votes") or 0
        no_votes = poll.get("no_votes") or 0
        total_votes = poll.get("total_votes") or 0
        pct_yes = (yes_votes / total_participants * 100) if total_participants > 0 else 0

        with st.expander(f"🗳️ Cancel Poll — {yes_votes}/{total_participants} voted Yes ({pct_yes:.0f}%)"):
            st.markdown(f"**Reason:** _{poll.get('reason', '')}_")
            st.markdown(f"Started by: **{poll.get('creator_name', '?')}**")

            # Progress bar
            st.markdown(f"""
            <div style="background:#e5e7eb;border-radius:8px;height:20px;margin:8px 0">
                <div style="background:#ef4444;width:{pct_yes:.0f}%;height:100%;
                            border-radius:8px;transition:width 0.3s">
                </div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.8rem">
                <span>✅ Yes: {yes_votes}</span>
                <span>Need: >{total_participants//2} votes</span>
                <span>❌ No: {no_votes}</span>
            </div>
            """, unsafe_allow_html=True)

            # Vote if participant and poll is active
            if poll.get("is_active") and is_participant(appt_id, user["id"]):
                my_vote = get_student_vote(poll["id"], user["id"])

                if my_vote is not None:
                    vote_label = "✅ Yes (cancel)" if my_vote == 1 else "❌ No (keep)"
                    st.info(f"Your vote: **{vote_label}**")
                    if st.button("Change my vote", key=f"change_vote_{poll['id']}"):
                        st.session_state[f"revoting_{poll['id']}"] = True
                        st.rerun()

                if my_vote is None or st.session_state.get(f"revoting_{poll['id']}"):
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✅ Yes — Cancel it", key=f"yes_{poll['id']}",
                                     use_container_width=True):
                            ok, msg, cancelled = submit_poll_vote(poll["id"], user["id"], 1)
                            st.session_state.pop(f"revoting_{poll['id']}", None)
                            if cancelled:
                                st.success("🚫 Majority reached! Appointment cancelled.")
                            else:
                                st.success("Vote recorded!")
                            st.rerun()
                    with col_no:
                        if st.button("❌ No — Keep it", key=f"no_{poll['id']}",
                                     use_container_width=True):
                            ok, msg, cancelled = submit_poll_vote(poll["id"], user["id"], 0)
                            st.session_state.pop(f"revoting_{poll['id']}", None)
                            st.success("Vote recorded!")
                            st.rerun()
            elif not poll.get("is_active"):
                st.success("Poll closed — appointment was cancelled by majority vote.")


# ── APPOINTMENT CARD ──────────────────────────────────────────────────────────

def _appointment_card(appt: dict, user: dict, show_poll=True):
    """Render a single appointment card."""
    icon, bg, color = STATUS_STYLE.get(appt["status"], ("❓", "#fff", "#000"))
    urg_icon, urg_label = URGENCY_STYLE.get(appt.get("urgency", "normal"), ("🟡", "Normal"))

    with st.container():
        description_html = (
            f"<p style='margin-top:0.4rem;color:var(--muted)'>{appt['description']}</p>"
            if appt.get('description') else ""
        )
        teacher_note_html = (
            f"<p style='margin-top:0.4rem'><b>Teacher's note:</b> {appt['teacher_note']}</p>"
            if appt.get('teacher_note') else ""
        )
        card_html = (
            '<div class="resource-card">'
            '<div style="display:flex;justify-content:space-between;align-items:flex-start">'
            '<div>'
            f'<strong style="font-size:1.05rem;color:var(--text)">📅 {appt["title"]}</strong>'
            '<div class="muted">'
            f'{appt.get("course_code") or "—"} · '
            f'🗓️ {appt["proposed_date"]} at {appt["proposed_time"]} · '
            f'{urg_icon} {urg_label} priority'
            '</div>'
            '<div class="muted">'
            f'Purpose: <b>{appt.get("purpose","—")}</b> · '
            f'👥 {appt.get("participant_count", 1)} participant(s)'
            '</div>'
            '</div>'
            f'<div>{_status_badge(appt["status"])}</div>'
            '</div>'
            f'{description_html}'
            f'{teacher_note_html}'
            '</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

        # Show teacher or student name depending on viewer
        if user["role"] == "student":
            st.caption(f"👨‍🏫 Teacher: **{appt.get('teacher_name', '?')}**")
        else:
            st.caption(f"👨‍🎓 Requested by: **{appt.get('creator_name', '?')}**")

        # Show participants
        with st.expander(f"👥 Participants ({appt.get('participant_count', 1)})"):
            participants = get_participants(appt["id"])
            for p in participants:
                st.markdown(f"• **{p['name']}** — Roll: {p.get('roll','—')} · Sem {p.get('semester','—')}")

            # Join button for students not yet in the group
            if (user["role"] == "student" and
                    appt["status"] in ("pending", "approved") and
                    not is_participant(appt["id"], user["id"])):
                if st.button("➕ Join this appointment", key=f"join_{appt['id']}"):
                    if join_appointment(appt["id"], user["id"]):
                        st.success("You joined!")
                        st.rerun()
                    else:
                        st.warning("Already joined.")

        # Cancel poll (students only, for active appointments)
        if show_poll and user["role"] == "student" and appt["status"] in ("pending", "approved"):
            _render_cancel_poll(appt, user)


# ── STUDENT PAGE ──────────────────────────────────────────────────────────────

def page_appointments_student(user: dict):
    st.markdown("<div class='page-header'>📅 My Appointments</div>",
                unsafe_allow_html=True)

    tab_mine, tab_book, tab_open = st.tabs([
        "📋 My Appointments", "📝 Book New", "🌐 Open Appointments"
    ])

    with tab_mine:
        appointments = get_appointments_for_student(user["id"])
        if not appointments:
            st.info("You have no appointments yet. Book one below!")
        else:
            # Filter by status
            status_filter = st.selectbox(
                "Filter", ["All", "pending", "approved", "cancelled", "rejected", "completed"],
                format_func=lambda x: x.title()
            )
            filtered = [a for a in appointments
                        if status_filter == "All" or a["status"] == status_filter]
            st.caption(f"{len(filtered)} appointment(s)")
            for appt in filtered:
                _appointment_card(appt, user, show_poll=True)

    with tab_book:
        _book_appointment_form(user)

    with tab_open:
        st.markdown("#### 🌐 Appointments You Can Join")
        st.caption("These are pending appointments from other students that you can join.")
        all_appts = get_all_appointments()
        open_appts = [
            a for a in all_appts
            if a["status"] == "pending"
            and not is_participant(a["id"], user["id"])
        ]
        if not open_appts:
            st.info("No open appointments to join right now.")
        for appt in open_appts:
            _appointment_card(appt, user, show_poll=False)


# ── TEACHER PAGE ──────────────────────────────────────────────────────────────

def page_appointments_teacher(user: dict):
    st.markdown("<div class='page-header'>📅 Appointments</div>",
                unsafe_allow_html=True)

    tab_requests, tab_book, tab_my = st.tabs([
        "📋 Student Requests", "📝 Schedule Office Hours", "📅 My Scheduled"
    ])

    # ── STUDENT REQUESTS ──
    with tab_requests:
        appointments = get_appointments_for_teacher(user["id"])

        if not appointments:
            st.info("No appointment requests from students yet.")
        else:
            status_filter = st.selectbox(
                "Filter by status",
                ["All", "pending", "approved", "rejected", "cancelled", "completed"],
                format_func=lambda x: x.title(),
                key="teacher_status_filter"
            )
            filtered = [a for a in appointments
                        if status_filter == "All" or a["status"] == status_filter]

            st.caption(f"{len(filtered)} appointment(s)")

            for appt in filtered:
                _appointment_card(appt, user, show_poll=False)

                # Teacher action buttons
                if appt["status"] == "pending":
                    st.markdown("**Respond to this request:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        with st.form(f"approve_form_{appt['id']}"):
                            note = st.text_input("Optional note to students",
                                                 placeholder="e.g. See you at Room 301")
                            if st.form_submit_button("✅ Approve", use_container_width=True):
                                update_appointment_status(appt["id"], "approved", note)
                                st.success("Appointment approved!")
                                st.rerun()
                    with col2:
                        with st.form(f"reject_form_{appt['id']}"):
                            note_r = st.text_input("Reason for rejection",
                                                    placeholder="e.g. I'm unavailable that day")
                            if st.form_submit_button("❌ Reject", use_container_width=True):
                                update_appointment_status(appt["id"], "rejected", note_r)
                                st.warning("Appointment rejected.")
                                st.rerun()

                elif appt["status"] == "approved":
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🎓 Mark Complete", key=f"complete_{appt['id']}",
                                     use_container_width=True):
                            update_appointment_status(appt["id"], "completed")
                            st.success("Marked as completed!")
                            st.rerun()
                    with col2:
                        if st.button("🚫 Cancel", key=f"teacher_cancel_{appt['id']}",
                                     use_container_width=True):
                            update_appointment_status(appt["id"], "cancelled",
                                                      "Cancelled by teacher.")
                            st.warning("Appointment cancelled.")
                            st.rerun()

                # Show cancel poll status for teacher (read-only)
                poll = get_cancel_poll(appt["id"])
                if poll:
                    total_participants = len(get_participants(appt["id"]))
                    yes_votes = poll.get("yes_votes") or 0
                    pct = (yes_votes / total_participants * 100) if total_participants > 0 else 0
                    st.info(f"🗳️ Cancel poll active — {yes_votes}/{total_participants} students voted Yes ({pct:.0f}%)")

                st.divider()

    # ── BOOK OFFICE HOURS ──
    with tab_book:
        st.markdown("#### 📝 Schedule Office Hours or Meeting")
        st.caption("Create an appointment for office hours, group sessions, or meetings with colleagues.")
        
        # Teachers can book with other teachers or leave it open for students
        courses = get_courses()
        if not courses:
            st.warning("No courses available. Ask an admin to add courses first.")
        else:
            course_options = {f"{c['code']} — {c['name']}": c["id"] for c in courses}

            with st.form("book_office_hours_form"):
                col1, col2 = st.columns(2)

                with col1:
                    title = st.text_input("Appointment Title *",
                                          placeholder="e.g. Office Hours, Research Discussion")
                    course_label = st.selectbox("Course (optional)", ["None"] + list(course_options.keys()))
                    from modules.auth import SEMESTER_OPTIONS
                    year_sem_label = st.selectbox("Semester *", list(SEMESTER_OPTIONS.keys()))
                    urgency = st.selectbox("Urgency", ["normal", "low", "high"],
                                           format_func=lambda x: _urgency_badge(x))

                with col2:
                    proposed_date = st.date_input(
                        "Preferred Date *",
                        min_value=bd_now().date() + timedelta(days=1),
                        value=bd_now().date() + timedelta(days=2)
                    )
                    proposed_time = st.time_input("Preferred Time *",
                                                  value=datetime.strptime("10:00", "%H:%M").time())
                    purpose = st.selectbox("Purpose *", [
                        "Office Hours", "Group Discussion", "Lab Session",
                        "Project Presentation", "Research Meeting", "Other"
                    ])
                    description = st.text_area("Details",
                                               placeholder="What will be discussed...",
                                               height=80)

                submitted = st.form_submit_button("📅 Schedule", use_container_width=True)

            if submitted:
                if not title:
                    st.error("Please enter a title.")
                else:
                    semester = SEMESTER_OPTIONS[year_sem_label]
                    course_id = course_options[course_label] if course_label != "None" else None
                    appt_id = create_appointment(
                        title=title,
                        description=f"[{year_sem_label}] {description}".strip(),
                        teacher_id=user["id"],
                        course_id=course_id,
                        proposed_date=str(proposed_date),
                        proposed_time=str(proposed_time)[:5],
                        purpose=purpose,
                        urgency=urgency,
                        created_by=user["id"]
                    )
                    st.success(f"✅ Office hours scheduled for **{year_sem_label}**!")
                    st.rerun()

    # ── MY SCHEDULED ──
    with tab_my:
        st.markdown("#### 📅 Your Scheduled Appointments")
        teacher_appointments = get_appointments_for_teacher(user["id"])
        my_appointments = [a for a in teacher_appointments if a["created_by"] == user["id"]]
        
        if not my_appointments:
            st.info("You haven't scheduled any office hours yet.")
        else:
            for appt in my_appointments:
                _appointment_card(appt, user, show_poll=False)
                
                if appt["status"] == "pending":
                    if st.button("✅ Open for students", key=f"open_{appt['id']}", 
                                 use_container_width=True):
                        update_appointment_status(appt["id"], "approved",
                                                  "Office hours open.")
                        st.success("Office hours now open!")
                        st.rerun()
                elif appt["status"] == "approved":
                    if st.button("🚫 Cancel Office Hours", key=f"cancel_office_{appt['id']}",
                                 use_container_width=True):
                        update_appointment_status(appt["id"], "cancelled",
                                                  "Cancelled by teacher.")
                        st.warning("Office hours cancelled.")
                        st.rerun()
                st.divider()


# ── ADMIN PAGE ────────────────────────────────────────────────────────────────

def page_appointments_admin():
    st.markdown("#### 📅 All Appointments")

    all_appts = get_all_appointments()
    if not all_appts:
        st.info("No appointments yet.")
        return

    import pandas as pd
    df = pd.DataFrame(all_appts)[[
        "id", "title", "teacher_name", "creator_name",
        "course_code", "proposed_date", "proposed_time",
        "purpose", "urgency", "status", "participant_count"
    ]]
    df.columns = ["ID", "Title", "Teacher", "Requested By", "Course",
                  "Date", "Time", "Purpose", "Urgency", "Status", "Participants"]
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Summary counts
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", len(all_appts))
    col2.metric("Pending", len([a for a in all_appts if a["status"] == "pending"]))
    col3.metric("Approved", len([a for a in all_appts if a["status"] == "approved"]))
    col4.metric("Cancelled", len([a for a in all_appts if a["status"] == "cancelled"]))