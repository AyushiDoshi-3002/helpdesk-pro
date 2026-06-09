"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DROP-IN REPLACEMENT FOR  _admin_doc_visibility()
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  In app.py, find the existing  def _admin_doc_visibility():
  block and replace THE ENTIRE FUNCTION with the one below.
  Nothing else in app.py needs to change.

  What changed:
  ─────────────
  • Tab 1 — Add Document : same form as before + list of
    existing docs (with delete button)
  • Tab 2 — Access Status :
      ⏳  Pending requests (employees submitted via
          Approval Pipeline) → admin can approve/reject here
      ✅  Active grants (direct access for Manager/CTO/CEO
          + approved employee requests, all with expiry)
      📂  Past requests (Approved / Rejected) — collapsed
  • REMOVED : Browse Documents, My Access, and the three
    nested Manage Library sub-tabs (everything except
    Add Document was stripped out)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def _admin_doc_visibility():
    st.markdown("### 📁 Document Visibility")
    st.markdown("---")

    tab1, tab2 = st.tabs(["➕ Add Document", "📋 Access Status"])

    # ══════════════════════════════════════════════════════════
    #  TAB 1 — Add Document
    # ══════════════════════════════════════════════════════════
    with tab1:
        st.markdown("#### Add a New Document")
        st.markdown(
            "<p style='color:#6b5f55; font-size:22px; font-family:EB Garamond,serif;'>"
            "Add a document to the library. Employees request access via the "
            "Approval Pipeline, and the request will appear in the Access Status tab.</p>",
            unsafe_allow_html=True,
        )

        with st.form("dv_add_doc_form", clear_on_submit=True):
            fa1, fa2 = st.columns(2)
            with fa1:
                doc_title    = st.text_input("Document Title *", placeholder="e.g. VPN Access Policy")
                doc_cat      = st.selectbox("Category", ["General","Security","HR","Finance","Engineering","Legal","Operations"])
                doc_sens     = st.selectbox("Sensitivity Level", ["Normal","Restricted","Confidential","Top Secret"])
            with fa2:
                doc_min_role = st.selectbox("Minimum Role to View", ROLE_HIERARCHY, index=0)
                doc_owner    = st.text_input("Owner ID", placeholder="e.g. EMP-0001")
                doc_url      = st.text_input("File URL (optional)", placeholder="https://…")
            doc_desc    = st.text_area("Description", placeholder="What does this document cover?", height=80)
            doc_preview = st.text_area(
                "Content Preview (shown to authorised users)",
                placeholder="A summary or excerpt of the document…",
                height=100,
            )
            submit_doc = st.form_submit_button("Add Document →", type="primary")

        if submit_doc:
            if not doc_title.strip():
                st.warning("Document title is required.")
            else:
                try:
                    added = db_add_document(
                        doc_title.strip(), doc_desc.strip(), doc_cat, doc_sens,
                        doc_min_role, doc_owner.strip(), doc_url.strip(), doc_preview.strip(),
                    )
                    st.success(f"✅ '{added['title']}' added — ID #{added['id']}.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed: {ex}")

        # ── All documents in library (with delete) ────────────────────────────
        st.markdown("---")
        st.markdown("#### 📚 Documents in Library")
        docs = db_get_documents()

        if not docs:
            st.info("No documents yet. Add one above.")
        else:
            st.markdown(
                f"<p style='font-family:DM Mono,monospace;font-size:16px;color:#9c8e82;"
                f"letter-spacing:0.06em;text-transform:uppercase;'>{len(docs)} document(s)</p>",
                unsafe_allow_html=True,
            )
            for doc in docs:
                doc_id      = doc["id"]
                sensitivity = doc.get("sensitivity", "Normal")
                min_role    = doc.get("min_role", "Employee")
                s_color     = _sensitivity_color(sensitivity)
                s_bg        = _sensitivity_bg(sensitivity)
                role_cls    = _role_badge_class(min_role)

                with st.expander(
                    f"📄 #{doc_id}  ·  {doc['title']}  ·  {doc.get('category','General')}  ·  {min_role}+  ·  {sensitivity}"
                ):
                    st.markdown(
                        f"<div style='display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;'>"
                        f"<span class='role-badge {role_cls}'>{min_role}+</span>"
                        f"<span style='display:inline-block;background:{s_bg};color:{s_color};"
                        f"border-radius:2px;padding:2px 10px;font-size:14px;font-family:DM Mono,monospace;"
                        f"font-weight:500;letter-spacing:0.08em;text-transform:uppercase;'>{sensitivity}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if doc.get("description"):
                        st.markdown(f"**Description:** {doc['description']}")
                    if doc.get("content_preview"):
                        st.markdown(f"**Preview:** {doc['content_preview'][:200]}…")
                    if doc.get("file_url"):
                        st.markdown(f"📎 **URL:** {doc['file_url']}")
                    st.markdown(
                        f"<small style='color:#9c8e82;font-family:DM Mono,monospace;'>"
                        f"Owner: {doc.get('owner_id','—')} · Added: {_to_ist(doc.get('created_at',''))}"
                        f"</small>",
                        unsafe_allow_html=True,
                    )
                    dc1, _ = st.columns([1, 5])
                    with dc1:
                        if st.button("Delete", key=f"dv_del_doc_{doc_id}", use_container_width=True):
                            try:
                                db_delete_document(doc_id)
                                st.warning("Deleted.")
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))

    # ══════════════════════════════════════════════════════════
    #  TAB 2 — Access Status
    # ══════════════════════════════════════════════════════════
    with tab2:
        st.markdown("#### 📋 Access Status")
        st.markdown("---")

        docs_map = {d["id"]: d for d in db_get_documents()}

        # ── Section 1: Pending requests (from Approval Pipeline) ─────────────
        pending_reqs = db_get_access_requests(status_filter="Pending")

        st.markdown(
            f"<p style='font-family:DM Mono,monospace;font-size:15px;color:#8b6914;"
            f"letter-spacing:0.06em;text-transform:uppercase;margin-bottom:8px;'>"
            f"⏳ {len(pending_reqs)} pending request(s) — submitted by employees via Approval Pipeline</p>",
            unsafe_allow_html=True,
        )

        if not pending_reqs:
            st.success("No pending access requests.", icon="✅")
        else:
            reviewer_id = st.text_input(
                "Your Reviewer ID *",
                placeholder="e.g. CTO-001",
                key="dv_tab2_reviewer_id",
            )
            for req in pending_reqs:
                doc           = docs_map.get(req["doc_id"])
                doc_title_str = doc["title"] if doc else f"Doc #{req['doc_id']}"
                req_id        = req["id"]

                with st.expander(
                    f"⏳ #{req_id}  ·  {req['user_id']} ({req['user_role']})  →  {doc_title_str}"
                ):
                    r1, r2 = st.columns(2)
                    with r1:
                        st.markdown(f"**Employee:** {req['user_id']}")
                        st.markdown(f"**Role:** {req['user_role']}")
                    with r2:
                        st.markdown(f"**Document:** {doc_title_str}")
                        st.markdown(f"**Requested:** {_to_ist(req.get('created_at',''))}")
                    st.markdown(f"**Reason:** {req.get('reason','—')}")

                    ac1, ac2, _ = st.columns([1.5, 1, 3])
                    with ac1:
                        if st.button(
                            "✅ Approve — 7-day Access",
                            key=f"dv2_approve_{req_id}",
                            use_container_width=True,
                            type="primary",
                        ):
                            if not reviewer_id.strip():
                                st.warning("Enter your Reviewer ID first.")
                            else:
                                db_review_access_request(
                                    req_id, "Approved", reviewer_id.strip(),
                                    doc_id=req["doc_id"],
                                    user_id=req["user_id"],
                                    user_role=req["user_role"],
                                )
                                st.success(f"✅ Access approved — {req['user_id']} now has 7-day access.")
                                st.rerun()
                    with ac2:
                        if st.button("❌ Reject", key=f"dv2_reject_{req_id}", use_container_width=True):
                            if not reviewer_id.strip():
                                st.warning("Enter your Reviewer ID first.")
                            else:
                                db_review_access_request(req_id, "Rejected", reviewer_id.strip())
                                st.warning(f"Request #{req_id} rejected.")
                                st.rerun()

        st.markdown("---")

        # ── Section 2: Active Grants ──────────────────────────────────────────
        # Shows: direct grants (Manager/CTO/CEO) + approved employee requests
        all_grants    = db_get_access_grants()
        now_utc       = datetime.now(timezone.utc)
        active_grants = []

        for g in all_grants:
            if g.get("status") != "Approved":
                continue
            try:
                exp = datetime.fromisoformat(g["expires_at"].replace("Z", "+00:00"))
                if exp > now_utc:
                    active_grants.append((g, exp))
            except Exception:
                pass

        st.markdown(
            f"<p style='font-family:DM Mono,monospace;font-size:15px;color:#3d5a4a;"
            f"letter-spacing:0.06em;text-transform:uppercase;margin-bottom:8px;'>"
            f"✅ {len(active_grants)} active grant(s) — direct (Manager/CTO/CEO) + approved requests</p>",
            unsafe_allow_html=True,
        )

        if not active_grants:
            st.info("No active access grants yet.")
        else:
            for grant, exp in active_grants:
                doc           = docs_map.get(grant["doc_id"])
                doc_title_str = doc["title"] if doc else f"Doc #{grant['doc_id']}"
                dl            = (exp - now_utc).days
                is_expiring   = dl <= 2
                color         = "#8b6914" if is_expiring else "#3d5a4a"
                expiry_label  = f"{'⚠ expiring soon — ' if is_expiring else ''}{dl}d remaining"
                granted_by    = grant.get("granted_by", "—")

                # Highlight direct senior access differently from pipeline approvals
                is_direct = "System" in granted_by or granted_by in ("Manager", "Tech Manager", "CTO", "CEO")
                border_color = "#3d5a4a" if not is_direct else "#2d3d4f"

                st.markdown(
                    f"<div style='background:var(--paper);border:1px solid var(--border);"
                    f"border-left:3px solid {border_color};border-radius:3px;"
                    f"padding:14px 20px;margin-bottom:8px;'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;'>"
                    f"<div>"
                    f"<span style='font-family:EB Garamond,serif;font-size:22px;font-weight:600;color:#1a1612;'>"
                    f"{doc_title_str}</span>"
                    f"&nbsp;&nbsp;"
                    f"<span style='font-family:DM Mono,monospace;font-size:13px;"
                    f"background:{'#f0e2b0' if is_expiring else '#d4e8dc'};"
                    f"color:{color};border:1px solid {'#d4b830' if is_expiring else '#7ab898'};"
                    f"border-radius:2px;padding:2px 10px;text-transform:uppercase;letter-spacing:0.06em;'>"
                    f"{expiry_label}</span>"
                    f"</div>"
                    f"</div>"
                    f"<div style='margin-top:6px;'>"
                    f"<small style='color:#9c8e82;font-family:DM Mono,monospace;font-size:16px;'>"
                    f"👤 <strong style='color:#3d3530;'>{grant['user_id']}</strong> ({grant['user_role']})"
                    f" &nbsp;·&nbsp; Granted by: {granted_by}"
                    f" &nbsp;·&nbsp; {_to_ist(grant.get('granted_at',''))}"
                    f"</small>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # ── Section 3: Past Requests (collapsed) ─────────────────────────────
        all_past = db_get_access_requests()
        past_reqs = [r for r in all_past if r.get("status") in ("Approved", "Rejected")]

        if past_reqs:
            with st.expander(f"📂 Past Requests — {len(past_reqs)} record(s)"):
                for req in past_reqs:
                    doc           = docs_map.get(req["doc_id"])
                    doc_title_str = doc["title"] if doc else f"Doc #{req['doc_id']}"
                    status        = req.get("status", "")
                    s_color       = {"Approved": "#3d5a4a", "Rejected": "#8b3a2a"}.get(status, "#6b5f55")

                    st.markdown(
                        f"<div class='doc-card' style='padding:12px 16px;margin-bottom:6px;'>"
                        f"<strong style='font-family:EB Garamond,serif;font-size:20px;'>"
                        f"#{req['id']}</strong>"
                        f" &nbsp;·&nbsp; {req['user_id']} ({req['user_role']})"
                        f" &nbsp;→&nbsp; {doc_title_str}"
                        f" &nbsp;&nbsp;"
                        f"<span style='color:{s_color};font-family:DM Mono,monospace;"
                        f"font-size:14px;text-transform:uppercase;letter-spacing:0.06em;'>"
                        f"{status}</span>"
                        f"<br>"
                        f"<small style='color:#9c8e82;font-family:DM Mono,monospace;font-size:16px;'>"
                        f"Reviewed by {req.get('reviewed_by','—')}"
                        f" &nbsp;·&nbsp; {_to_ist(req.get('reviewed_at',''))}"
                        f"</small>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
