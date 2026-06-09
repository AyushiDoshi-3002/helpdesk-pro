"""
Run this script next to app.py to fix the IndentationError (updated for v2).
    python3 fix_app.py
Saves a backup as app.py.bak before patching.
"""
import shutil, sys, pathlib

TARGET = pathlib.Path("app.py")
if not TARGET.exists():
    sys.exit("ERROR: app.py not found in the current directory.")

shutil.copy(TARGET, TARGET.with_suffix(".py.bak"))

src = TARGET.read_text(encoding="utf-8")

# ── The broken block (two nested else-with-no-body, stray else at wrong level)
BROKEN = (
    '                                if not reason.strip(): st.warning("Please provide a reason for the request.")\n'
    '                                else:\n'
    '                        else:\n'
    '                                    try:\n'
    '                                        result = db_submit_access_request(\n'
    '                                            doc_id=doc_id,\n'
    '                                            user_id=viewer_id.strip(),\n'
    '                                            user_role=viewer_role,\n'
    '                                            reason=reason.strip(),\n'
    '                                        )\n'
    '                                        if result is None:\n'
    '                                            st.info("You already have a pending request for this document.")\n'
    '                                        else:\n'
    '                                            st.success(\n'
    "                                                f\"\u2705 Access request submitted for **{doc['title']}**. \"\n"
    '                                                "Your request is in the approval pipeline \u2014 you will "\n'
    '                                                "receive access only after a Manager or above approves it."\n'
    '                                            )\n'
    '                                    except Exception as ex:\n'
    '                                        st.error(f"Failed to submit request: {ex}")'
)

# ── The correct replacement (properly indented, stray else removed)
FIXED = (
    '                                if not reason.strip():\n'
    '                                    st.warning("Please provide a reason for the request.")\n'
    '                                else:\n'
    '                                    try:\n'
    '                                        result = db_submit_access_request(\n'
    '                                            doc_id=doc_id,\n'
    '                                            user_id=viewer_id.strip(),\n'
    '                                            user_role=viewer_role,\n'
    '                                            reason=reason.strip(),\n'
    '                                        )\n'
    '                                        if result is None:\n'
    '                                            st.info("You already have a pending request for this document.")\n'
    '                                        else:\n'
    '                                            st.success(\n'
    "                                                f\"\u2705 Access request submitted for **{doc['title']}**. \"\n"
    '                                                "Your request is in the approval pipeline \u2014 you will "\n'
    '                                                "receive access only after a Manager or above approves it."\n'
    '                                            )\n'
    '                                    except Exception as ex:\n'
    '                                        st.error(f"Failed to submit request: {ex}")'
)

if BROKEN not in src:
    sys.exit(
        "ERROR: Could not find the broken block — the file may already be fixed "
        "or was saved with different whitespace. No changes made.\n"
        "Tip: make sure you saved the file exactly as shown in the GitHub editor."
    )

patched = src.replace(BROKEN, FIXED, 1)
TARGET.write_text(patched, encoding="utf-8")
print("✅  app.py patched successfully. Backup saved as app.py.bak")
