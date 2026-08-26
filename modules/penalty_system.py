"""
penalty_system.py - Tiered penalty, reputation score, appeals & peer reports
- Admin/Teachers issue violations
- Students get notified + can appeal
- Peer reports reviewed by admin
- Reputation score visible on profile
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import (
    get_user_penalty_status, get_reputation_badge, get_reputation_log,
    get_user_violations, issue_violation, resolve_violation,
    reduce_warning_points, get_all_violations,
    submit_appeal, get_appeals, get_user_appeals, review_appeal,
    submit_peer_report, get_peer_reports, update_peer_report_status,
    get_all_users, get_user_by_id, VIOLATION_TYPES, VIOLATION_POINTS,
    REPUTATION_DEDUCTION, REPORT_TYPE_OPTIONS, violation_type_from_label
)
from modules.file_manager import (
    save_evidence_files, render_evidence_thumbnails,
    EVIDENCE_MAX_FILES, EVIDENCE_MAX_SIZE_MB
)


# ── SHARED: REPUTATION CARD ───────────────────────────────────────────────────

def render_reputation_card(user_id, viewer_role="student"):
    """Show reputation score, badge, warning points for any user."""
    status = get_user_penalty_status(user_id)
    if not status:
        return

    score = status.get("reputation_score", 100)
    points = status.get("warning_points", 0)
    badge_icon, badge_label = get_reputation_badge(score)

    # Color based on score
    color = "#065f46" if score >= 80 else "#92400e" if score >= 40 else "#991b1b"
    bar_color = "#10b981" if score >= 80 else "#f59e0b" if score >= 40 else "#ef4444"

    st.markdown(f"""
    <div class="resource-card" style="padding:1.2rem">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
                <div style="font-size:2rem">{badge_icon}</div>
                <div style="font-size:1.1rem;font-weight:700;color:{color}">{badge_label}</div>
                <div class="muted">Reputation Score</div>
            </div>
            <div style="text-align:right">
                <div style="font-size:2.5rem;font-weight:800;color:{color}">{score}</div>
                <div class="muted">/ 100</div>
            </div>
        </div>
        <div style="background:#e5e7eb;border-radius:8px;height:12px;margin:10px 0">
            <div style="background:{bar_color};width:{score}%;height:100%;border-radius:8px"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.85rem">
            <span>⚠️ Warning Points: <b>{points}</b></span>
            <span>{'🚫 Suspended' if status.get('suspended_until') else '✅ Active'}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Suspension notice
    if status.get("suspended_until"):
        st.error(f"🚫 Account suspended until **{status['suspended_until']}**\n\n"
                 f"Reason: {status.get('suspension_reason', 'Violation of platform rules')}")
    elif not status.get("is_active"):
        st.error("🚫 Account permanently banned.")

    # Warning points progress
    if points > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.progress(min(points / 15, 1.0),
                        text=f"⚠️ {points}/15 warning points")
        with col2:
            if points >= 10:
                st.warning("🔴 Suspension threshold reached!")
            elif points >= 7:
                st.warning("⚠️ Approaching suspension (10 pts)")


# ── STUDENT: MY PROFILE / REPUTATION ─────────────────────────────────────────

def page_my_profile(user: dict):
    st.markdown("<div class='page-header'>👤 My Profile & Reputation</div>",
                unsafe_allow_html=True)

    tab_rep, tab_violations, tab_appeals, tab_report = st.tabs([
        "⭐ My Reputation", "⚠️ My Violations", "📋 My Appeals", "🚩 Report Someone"
    ])

    # ── REPUTATION TAB ──
    with tab_rep:
        render_reputation_card(user["id"])
        st.divider()
        st.markdown("#### 📜 Reputation History")
        log = get_reputation_log(user["id"])
        if log:
            df = pd.DataFrame(log)[["change", "reason", "old_score", "new_score", "created_at"]]
            df.columns = ["Change", "Reason", "Before", "After", "Date"]
            df["Change"] = df["Change"].apply(lambda x: f"{'🔴 -' if x < 0 else '🟢 +'}{abs(x)}")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No reputation changes yet — keep contributing positively! 🌟")

        st.divider()
        st.markdown("#### 🎖️ Badge Tiers")
        tiers = [
            ("🏆", "Trusted Member", "100", "Fastest approvals, verified badge"),
            ("⭐", "Good Standing", "80–99", "Priority upload queue"),
            ("🔵", "Regular Member", "60–79", "Standard access"),
            ("⚠️", "At Risk", "40–59", "Upload moderation enabled"),
            ("🔴", "Restricted", "Below 40", "Limited platform access"),
        ]
        for icon, label, score_range, benefit in tiers:
            current = get_reputation_badge(user.get("reputation_score", 100))[1] == label
            border = "border:2px solid #2c5f8a;" if current else ""
            here_tag = (
                "<span style='color:#2c5f8a;font-weight:600'> ← You are here</span>"
                if current else ""
            )
            tier_html = (
                f'<div class="resource-card" style="padding:0.7rem 1rem;{border}">'
                f'<span style="font-size:1.2rem">{icon}</span>'
                f'<strong> {label}</strong>'
                f'<span class="muted"> · Score: {score_range} · {benefit}</span>'
                f'{here_tag}'
                '</div>'
            )
            st.markdown(tier_html, unsafe_allow_html=True)

    # ── VIOLATIONS TAB ──
    with tab_violations:
        violations = get_user_violations(user["id"])
        if not violations:
            st.success("✅ No violations on your record. Keep it up!")
        else:
            for v in violations:
                sev_color = {"minor": "#92400e", "moderate": "#b45309", "severe": "#991b1b"}
                v_label = VIOLATION_TYPES.get(v["violation_type"], ("Unknown", "minor"))[0]
                st.markdown(f"""
                <div class="resource-card">
                    <div style="display:flex;justify-content:space-between">
                        <div>
                            <strong>⚠️ {v_label}</strong>
                            <span style="background:#fee2e2;color:{sev_color.get(v['severity'],'#991b1b')};
                                  padding:2px 8px;border-radius:10px;font-size:0.75rem;margin-left:8px">
                                {v['severity'].title()} · +{v['points']} pts
                            </span>
                        </div>
                        <span class="muted">{v['created_at'][:10]}</span>
                    </div>
                    <div class="muted">Issued by: {v['issued_by_name']}</div>
                    <p style="margin-top:0.4rem">{v['description']}</p>
                </div>
                """, unsafe_allow_html=True)

                # Appeal button if active
                if v["status"] == "active":
                    if st.button(f"📋 Appeal this violation", key=f"appeal_btn_{v['id']}"):
                        st.session_state[f"appealing_{v['id']}"] = True

                    if st.session_state.get(f"appealing_{v['id']}"):
                        with st.form(f"appeal_form_{v['id']}"):
                            reason = st.text_area(
                                "Explain why you're appealing",
                                placeholder="Provide your side of the story...",
                                height=100
                            )
                            evidence_upload = st.file_uploader(
                                "Attach evidence (optional)",
                                type=["png", "jpg", "jpeg"],
                                accept_multiple_files=True,
                                key=f"appeal_evidence_{v['id']}",
                                help=f"Up to {EVIDENCE_MAX_FILES} images (PNG/JPG, max "
                                     f"{EVIDENCE_MAX_SIZE_MB}MB each) that support your case."
                            )
                            if st.form_submit_button("Submit Appeal", use_container_width=True):
                                if reason.strip():
                                    stored, errors = save_evidence_files(evidence_upload, user["id"])
                                    for err in errors:
                                        st.warning(err)
                                    ok, msg = submit_appeal(
                                        user["id"], v["id"], reason, ",".join(stored)
                                    )
                                    if ok:
                                        st.success(msg)
                                        st.session_state.pop(f"appealing_{v['id']}", None)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                                else:
                                    st.warning("Please provide a reason.")
                elif v["status"] == "appealed":
                    st.info("📋 Appeal submitted — awaiting admin review.")
                elif v["status"] == "resolved":
                    st.success("✅ Resolved")

    # ── APPEALS TAB ──
    with tab_appeals:
        appeals = get_user_appeals(user["id"])
        if not appeals:
            st.info("You have no appeals submitted.")
        else:
            for a in appeals:
                status_color = {
                    "pending": "#92400e", "approved": "#065f46", "rejected": "#991b1b"
                }
                color = status_color.get(a["status"], "#374151")
                admin_response_html = (
                    f"<p><b>Admin response:</b> {a['admin_response']}</p>"
                    if a.get('admin_response') else ""
                )
                card_html = (
                    '<div class="resource-card">'
                    '<div style="display:flex;justify-content:space-between">'
                    f"<strong>📋 Appeal — {a.get('violation_type','Violation').replace('_',' ').title()}</strong>"
                    f'<span style="color:{color};font-weight:600">{a["status"].title()}</span>'
                    '</div>'
                    f'<p class="muted">Your reason: {a["reason"]}</p>'
                    f'{admin_response_html}'
                    f'<span class="muted">{a["created_at"][:10]}</span>'
                    '</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
                render_evidence_thumbnails(a.get("evidence_files", ""), caption="Your evidence")

    # ── PEER REPORT TAB ──
    with tab_report:
        st.markdown("#### 🚩 Report a User")
        st.caption("Reports are reviewed by admins. False reports may result in penalties.")

        users = get_all_users()
        reportable = [u for u in users if u["id"] != user["id"]]
        user_map = {f"{u['name']} ({u['role']})": u["id"] for u in reportable}

        with st.form("peer_report_form"):
            reported_label = st.selectbox("Who are you reporting?", list(user_map.keys()))
            report_type = st.selectbox("Type of violation", REPORT_TYPE_OPTIONS)
            description = st.text_area("Describe the issue *",
                                       placeholder="Be specific — what did they do?",
                                       height=100)
            evidence_upload = st.file_uploader(
                "Attach evidence (optional)",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key="peer_report_evidence",
                help=f"Up to {EVIDENCE_MAX_FILES} images (PNG/JPG, max "
                     f"{EVIDENCE_MAX_SIZE_MB}MB each) that support your report."
            )
            submitted = st.form_submit_button("🚩 Submit Report", use_container_width=True)

        if submitted:
            if description.strip():
                stored, errors = save_evidence_files(evidence_upload, user["id"])
                for err in errors:
                    st.warning(err)
                ok, msg = submit_peer_report(
                    user["id"], user_map[reported_label],
                    report_type, description.strip(),
                    evidence_files=",".join(stored)
                )
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.warning("Please describe the issue.")


# ── TEACHER: ISSUE VIOLATION ──────────────────────────────────────────────────

def page_issue_violation(user: dict):
    st.markdown("<div class='page-header'>⚠️ Issue Violation</div>",
                unsafe_allow_html=True)

    if user["role"] not in ("teacher", "admin"):
        st.error("Access denied.")
        return

    st.caption("Issue warnings to students for platform violations.")

    users = get_all_users()
    students = [u for u in users if u["role"] == "student"]
    student_map = {f"{u['name']} ({u.get('student_id','')})": u["id"] for u in students}

    col1, col2 = st.columns(2)
    with col1:
        selected_student = st.selectbox("Select Student", list(student_map.keys()))
        student_id = student_map[selected_student]

        # Show their current status
        status = get_user_penalty_status(student_id)
        if status:
            badge_icon, badge_label = get_reputation_badge(status.get("reputation_score", 100))
            st.info(f"{badge_icon} **{badge_label}** · "
                    f"Rep: {status.get('reputation_score', 100)} · "
                    f"Warning pts: {status.get('warning_points', 0)}/15")

    with col2:
        violation_key = st.selectbox(
            "Violation Type",
            list(VIOLATION_TYPES.keys()),
            format_func=lambda k: f"{VIOLATION_TYPES[k][0]} ({VIOLATION_TYPES[k][1]})"
        )
        severity = VIOLATION_TYPES[violation_key][1]
        pts = VIOLATION_POINTS[severity]
        rep_loss = REPUTATION_DEDUCTION[severity]
        st.warning(f"This will add **+{pts} warning points** and **-{rep_loss} reputation**")

    description = st.text_area("Reason / Description *",
                               placeholder="Explain the violation clearly...",
                               height=100)

    if st.button("⚠️ Issue Violation", use_container_width=True, type="primary"):
        if description.strip():
            ok, msg = issue_violation(
                student_id, user["id"], violation_key, description.strip()
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        else:
            st.warning("Please provide a description.")

    st.divider()
    st.markdown("#### 📋 Recent Violations You Issued")
    all_v = get_all_violations()
    mine = [v for v in all_v if v.get("issued_by") == user["id"]][:10]
    if mine:
        for v in mine:
            v_label = VIOLATION_TYPES.get(v["violation_type"], ("Unknown",))[0]
            st.markdown(f"• **{v['user_name']}** — {v_label} "
                        f"· {v['severity']} · {v['created_at'][:10]}")
    else:
        st.caption("No violations issued yet.")


# ── ADMIN: FULL PENALTY PANEL ─────────────────────────────────────────────────

def page_admin_penalties():
    st.markdown("#### ⚠️ Penalty Management")

    tab_v, tab_appeals, tab_reports, tab_users_rep = st.tabs([
        "📋 All Violations", "📨 Appeals", "🚩 Peer Reports", "👥 User Reputations"
    ])

    # ── ALL VIOLATIONS ──
    with tab_v:
        violations = get_all_violations()
        if not violations:
            st.info("No violations yet.")
        else:
            status_filter = st.selectbox("Filter", ["All", "active", "appealed", "resolved"],
                                         key="viol_filter")
            filtered = [v for v in violations
                        if status_filter == "All" or v["status"] == status_filter]
            st.caption(f"{len(filtered)} violation(s)")

            for v in filtered:
                v_label = VIOLATION_TYPES.get(v["violation_type"], ("Unknown",))[0]
                with st.expander(f"⚠️ {v['user_name']} — {v_label} · {v['severity']} · {v['created_at'][:10]}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**User:** {v['user_name']} ({v['user_role']})")
                        st.write(f"**Issued by:** {v['issued_by_name']}")
                        st.write(f"**Points:** +{v['points']}")
                        st.write(f"**Status:** {v['status'].title()}")
                    with col2:
                        st.write(f"**Description:** {v['description']}")
                    if v["status"] == "active":
                        if st.button("✅ Mark Resolved", key=f"res_v_{v['id']}"):
                            resolve_violation(v["id"])
                            st.success("Resolved.")
                            st.rerun()

    # ── APPEALS ──
    with tab_appeals:
        appeals = get_appeals()
        pending = [a for a in appeals if a["status"] == "pending"]
        st.caption(f"{len(pending)} pending appeal(s)")

        for a in appeals:
            status_icon = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(a["status"], "❓")
            with st.expander(f"{status_icon} {a['user_name']} — {a['created_at'][:10]} · {a['status'].title()}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**User:** {a['user_name']} ({a['user_email']})")
                    st.write(f"**Warning Points:** {a['warning_points']}")
                    st.write(f"**Reputation:** {a['reputation_score']}")
                    st.write(f"**Violation:** {a.get('violation_type','—').replace('_',' ').title()}")
                with col2:
                    st.write(f"**Appeal Reason:**")
                    st.info(a["reason"])

                render_evidence_thumbnails(a.get("evidence_files", ""),
                                           caption="Evidence from appellant")

                if a["status"] == "pending":
                    with st.form(f"review_appeal_{a['id']}"):
                        response = st.text_area("Admin Response *",
                                                placeholder="Explain your decision...")
                        c1, c2 = st.columns(2)
                        with c1:
                            approve = st.form_submit_button("✅ Approve Appeal",
                                                            use_container_width=True)
                        with c2:
                            reject = st.form_submit_button("❌ Reject Appeal",
                                                           use_container_width=True)
                    if approve and response:
                        review_appeal(a["id"], st.session_state["user"]["id"],
                                      "approved", response)
                        st.success("Appeal approved!")
                        st.rerun()
                    elif reject and response:
                        review_appeal(a["id"], st.session_state["user"]["id"],
                                      "rejected", response)
                        st.warning("Appeal rejected.")
                        st.rerun()
                elif a.get("admin_response"):
                    st.write(f"**Admin Response:** {a['admin_response']}")

    # ── PEER REPORTS ──
    with tab_reports:
        reports = get_peer_reports()
        pending_r = [r for r in reports if r["status"] == "pending"]
        st.caption(f"{len(pending_r)} pending report(s)")

        for r in reports:
            status_icon = {"pending": "⏳", "actioned": "✅",
                           "dismissed": "❌", "reviewed": "👁️"}.get(r["status"], "❓")
            with st.expander(f"{status_icon} Report against {r['reported_name']} "
                             f"· {r['report_type']} · {r['created_at'][:10]}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Reported:** {r['reported_name']} ({r['reported_role']})")
                    st.write(f"**Rep Score:** {r['reputation_score']}")
                    st.write(f"**Warning Pts:** {r['warning_points']}")
                    st.write(f"**Reported by:** {r['reporter_name']}")
                with col2:
                    st.write(f"**Type:** {r['report_type']}")
                    st.info(r["description"])

                render_evidence_thumbnails(r.get("evidence_files", ""),
                                           caption="Evidence from reporter")

                if r["status"] == "pending":
                    col_a, col_b, col_c, col_d = st.columns(4)
                    with col_a:
                        if st.button("⚠️ Issue Violation", key=f"rpt_act_{r['id']}"):
                            st.session_state[f"issue_from_report_{r['id']}"] = True
                    with col_b:
                        if st.button("👁️ Mark Reviewed", key=f"rpt_rev_{r['id']}"):
                            update_peer_report_status(r["id"], "reviewed",
                                                      st.session_state["user"]["id"])
                            st.rerun()
                    with col_c:
                        if st.button("❌ Dismiss", key=f"rpt_dis_{r['id']}",
                                     help="No violation was found — reporter is not penalized."):
                            update_peer_report_status(r["id"], "dismissed",
                                                      st.session_state["user"]["id"])
                            st.rerun()
                    with col_d:
                        if st.button("🚫 Dismiss as False Report", key=f"rpt_false_{r['id']}",
                                     help="Report was baseless/malicious — penalizes the reporter."):
                            update_peer_report_status(r["id"], "dismissed",
                                                      st.session_state["user"]["id"])
                            issue_violation(
                                r["reporter_id"], st.session_state["user"]["id"],
                                "fake_report",
                                f"Filed a false report against {r['reported_name']} "
                                f"(claimed: {r['report_type']})"
                            )
                            st.success("Report dismissed and reporter penalized for a false report.")
                            st.rerun()

                    if st.session_state.get(f"issue_from_report_{r['id']}"):
                        with st.form(f"viol_from_report_{r['id']}"):
                            v_keys = list(VIOLATION_TYPES.keys())
                            # Default the type to whatever the reporter actually
                            # selected, instead of always falling back to the
                            # first entry in the list — admin can still override.
                            default_key = violation_type_from_label(r["report_type"])
                            default_idx = v_keys.index(default_key) if default_key in v_keys else 0
                            v_type = st.selectbox(
                                "Violation type",
                                v_keys,
                                index=default_idx,
                                format_func=lambda k: VIOLATION_TYPES[k][0]
                            )
                            v_desc = st.text_area("Description", value=r["description"])
                            if st.form_submit_button("Issue Violation"):
                                issue_violation(r["reported_user_id"],
                                                st.session_state["user"]["id"],
                                                v_type, v_desc)
                                update_peer_report_status(r["id"], "actioned",
                                                          st.session_state["user"]["id"])
                                st.session_state.pop(f"issue_from_report_{r['id']}", None)
                                st.success("Violation issued!")
                                st.rerun()

    # ── USER REPUTATIONS ──
    with tab_users_rep:
        st.markdown("#### 👥 All User Reputation Scores")
        users = get_all_users()
        for u in users:
            if u["role"] == "admin":
                continue
            badge_icon, badge_label = get_reputation_badge(u.get("reputation_score", 100))
            with st.expander(f"{badge_icon} {u['name']} ({u['role']}) · "
                             f"Rep: {u.get('reputation_score',100)} · "
                             f"Pts: {u.get('warning_points',0)}/15"):
                col1, col2 = st.columns(2)
                with col1:
                    render_reputation_card(u["id"], viewer_role="admin")
                with col2:
                    st.markdown("**Adjust Warning Points**")
                    with st.form(f"adj_pts_{u['id']}"):
                        pts_remove = st.number_input("Remove points", 1, 15, 1)
                        reason_adj = st.text_input("Reason")
                        if st.form_submit_button("Reduce Points"):
                            if reason_adj:
                                reduce_warning_points(
                                    u["id"], pts_remove, reason_adj,
                                    st.session_state["user"]["id"]
                                )
                                st.success("Points reduced!")
                                st.rerun()