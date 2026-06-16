import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime

from config import (
    BASE_DIR, SHEET_ID, SUPER_ADMIN_EMAIL,
    COL, TERMS_HEADER, VOTES_HEADER, SOURCE_HEADER,
    AUDIT_LOG_HEADER, MEMBERS_HEADER,
    VALID_VOTES, strip_tone_marks,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds  = Credentials.from_service_account_file(
    os.path.join(BASE_DIR, 'credentials.json'), scopes=SCOPES
)
gs_client = gspread.authorize(creds)


# ── Sheet accessors ───────────────────────────────────────────────────────

def get_terms_sheet():
    return gs_client.open_by_key(SHEET_ID).worksheet("Terms")

def get_votes_sheet():
    return gs_client.open_by_key(SHEET_ID).worksheet("Votes")

def get_members_sheet():
    return gs_client.open_by_key(SHEET_ID).worksheet("Members")

def get_source_sheet():
    return gs_client.open_by_key(SHEET_ID).worksheet("Sources")

def get_audit_sheet():
    return gs_client.open_by_key(SHEET_ID).worksheet("Audit_Log")


# ── Audit ─────────────────────────────────────────────────────────────────

def write_audit(term_id, term_chinese, user_email, user_name, action_type,
                field_changed="", old_value="", new_value="", details=""):
    """Append one row to Audit_Log. Swallows exceptions so audit never breaks the main flow."""
    try:
        now     = datetime.now()
        aid     = "A" + now.strftime("%Y%m%d%H%M%S%f")
        now_str = now.strftime("%Y-%m-%d %H:%M")
        get_audit_sheet().append_row([
            aid, now_str, term_id, term_chinese, user_email, user_name,
            action_type, field_changed, old_value, new_value, details
        ])
    except Exception:
        pass


# ── Term helpers ──────────────────────────────────────────────────────────

def next_term_id(sheet):
    rows = sheet.get_all_values()
    if len(rows) <= 1:
        return "T000001"
    ids  = [r[0] for r in rows[1:] if r[0].startswith("T")]
    if not ids:
        return "T000001"
    nums = [int(i[1:]) for i in ids if i[1:].isdigit()]
    return f"T{(max(nums)+1):06d}" if nums else "T000001"


def recalculate_auto_selections(term_id, votes_rows, terms_sheet):
    """Recompute TranslationFirst/Second from votes; skips finalized terms."""
    tallies = {k: 0 for k in VALID_VOTES}
    for v in votes_rows:
        t = v.get("ChosenTranslation", "")
        if v.get("TermID") == term_id and t in tallies:
            tallies[t] += 1

    ranked = sorted(tallies.items(), key=lambda x: x[1], reverse=True)
    first  = ranked[0][0] if ranked[0][1] > 1 else ""
    second = ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 1 else ""

    rows = terms_sheet.get_all_values()
    for i, row in enumerate(rows):
        if i == 0:
            continue
        if row[0] == term_id:
            status_val = row[COL["status"] - 1] if len(row) >= COL["status"] else ""
            if status_val == "finalized":
                ex_first  = row[COL["trans_first"]  - 1] if len(row) >= COL["trans_first"]  else ""
                ex_second = row[COL["trans_second"] - 1] if len(row) >= COL["trans_second"] else ""
                return ex_first, ex_second
            terms_sheet.update_cell(i + 1, COL["trans_first"],  first)
            terms_sheet.update_cell(i + 1, COL["trans_second"], second)
            break
    return first, second


# ── Member helpers ────────────────────────────────────────────────────────

def lookup_member(email):
    """Return role string for email, or None if not a member."""
    if email.lower() == SUPER_ADMIN_EMAIL.lower():
        return "admin"
    try:
        rows = get_members_sheet().get_all_records()
        for r in rows:
            if r.get("Email", "").lower() == email.lower():
                return r.get("Role", "member")
    except Exception:
        pass
    return None


# ── Schema init / migration ───────────────────────────────────────────────

def _migrate_term_ids(wb):
    """Migrate short Term IDs (T001) to 6-digit format (T000001). Idempotent."""
    ts = wb.worksheet("Terms")
    vs = wb.worksheet("Votes")
    all_rows = ts.get_all_values()
    migrations = {}
    for i, row in enumerate(all_rows[1:], start=2):
        old_id = row[0] if row else ""
        if old_id.startswith("T"):
            suffix = old_id[1:]
            if suffix.isdigit() and len(suffix) < 6:
                new_id = f"T{int(suffix):06d}"
                migrations[old_id] = new_id
                ts.update_cell(i, 1, new_id)
    if not migrations:
        return
    vote_rows = vs.get_all_values()
    for i, row in enumerate(vote_rows[1:], start=2):
        if row and row[0] in migrations:
            vs.update_cell(i, 1, migrations[row[0]])


def ensure_headers():
    """Create missing sheets and patch existing Terms sheet with any new columns."""
    wb          = gs_client.open_by_key(SHEET_ID)
    sheet_names = [s.title for s in wb.worksheets()]

    if "Terms" not in sheet_names:
        ts = wb.add_worksheet(title="Terms", rows=1000, cols=26)
        ts.append_row(TERMS_HEADER)
    else:
        ts = wb.worksheet("Terms")
        existing = ts.row_values(1)
        if "LastModifiedDate" in existing:
            ts.update_cell(1, existing.index("LastModifiedDate") + 1, "LastModifiedTime")
            existing[existing.index("LastModifiedDate")] = "LastModifiedTime"
        for i in range(len(existing), len(TERMS_HEADER)):
            ts.update_cell(1, i + 1, TERMS_HEADER[i])
        # Backfill RomanizationPlain for existing rows
        all_rows = ts.get_all_values()
        if len(all_rows) > 1:
            hdr    = all_rows[0]
            py_idx = hdr.index("Pinyin") if "Pinyin" in hdr else None
            rp_idx = hdr.index("RomanizationPlain") if "RomanizationPlain" in hdr else None
            if py_idx is not None and rp_idx is not None:
                for i, row in enumerate(all_rows[1:], start=2):
                    py_val = row[py_idx] if py_idx < len(row) else ""
                    rp_val = row[rp_idx] if rp_idx < len(row) else ""
                    if py_val and not rp_val:
                        ts.update_cell(i, rp_idx + 1, strip_tone_marks(py_val))
        _migrate_term_ids(wb)

    if "Votes" not in sheet_names:
        vs = wb.add_worksheet(title="Votes", rows=2000, cols=5)
        vs.append_row(VOTES_HEADER)

    if "Members" not in sheet_names:
        ms = wb.add_worksheet(title="Members", rows=200, cols=7)
        ms.append_row(MEMBERS_HEADER)
        ms.append_row([SUPER_ADMIN_EMAIL, "admin", "system",
                       datetime.now().strftime("%Y-%m-%d %H:%M"), "", ""])
    else:
        ms = wb.worksheet("Members")
        existing_m = ms.row_values(1)
        for i in range(len(existing_m), len(MEMBERS_HEADER)):
            ms.update_cell(1, i + 1, MEMBERS_HEADER[i])

    if "Sources" not in sheet_names:
        ss = wb.add_worksheet(title="Sources", rows=200, cols=5)
        ss.append_row(SOURCE_HEADER)

    if "Audit_Log" not in sheet_names:
        al = wb.add_worksheet(title="Audit_Log", rows=5000, cols=11)
        al.append_row(AUDIT_LOG_HEADER)
