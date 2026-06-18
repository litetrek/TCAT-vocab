import logging
from datetime import datetime

from db import supabase
import sheets

logger = logging.getLogger(__name__)


def _v(row, key):
    val = row.get(key)
    return val if val is not None else ""


def _fmt_ts(val):
    if not val:
        return ""
    s = str(val).replace("T", " ")
    if "+" in s:
        s = s[:s.index("+")]
    if "." in s:
        s = s[:s.index(".")]
    return s[:16]


def get_term_audit(term_id):
    """Return audit entries for a term in the existing frontend CamelCase shape."""
    result = (
        supabase.table("audit_log")
        .select("*")
        .eq("term_id", term_id)
        .order("timestamp", desc=True)
        .execute()
    )
    entries = []
    for r in result.data:
        audit_id = _v(r, "legacy_audit_id") or f"A{r.get('id', '')}"
        entries.append({
            "AuditID":     audit_id,
            "Timestamp":   _fmt_ts(_v(r, "timestamp")),
            "TermID":      _v(r, "term_id"),
            "TermChinese": _v(r, "term_chinese"),
            "UserEmail":   _v(r, "user_email"),
            "UserName":    _v(r, "user_name"),
            "ActionType":  _v(r, "action_type"),
            "FieldChanged": _v(r, "field_changed"),
            "OldValue":    _v(r, "old_value"),
            "NewValue":    _v(r, "new_value"),
            "Details":     _v(r, "details"),
        })
    return entries


def write_audit(term_id, term_chinese, user_email, user_name, action_type,
                field_changed="", old_value="", new_value="", details=""):
    """
    Write one audit entry to Supabase audit_log, then mirror to the Audit_Log sheet.
    Never raises — audit writes must never break the main request flow.
    """
    try:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M")

        try:
            supabase.table("audit_log").insert({
                "timestamp":     now.isoformat(),
                "term_id":       term_id       or None,
                "term_chinese":  term_chinese  or None,
                "user_email":    user_email    or None,
                "user_name":     user_name     or None,
                "action_type":   action_type   or None,
                "field_changed": field_changed or None,
                "old_value":     old_value     or None,
                "new_value":     new_value     or None,
                "details":       details       or None,
            }).execute()
        except Exception as exc:
            logger.error("Audit Supabase write failed: %s", exc)

        try:
            aid = "A" + now.strftime("%Y%m%d%H%M%S%f")
            sheets.get_audit_sheet().append_row([
                aid, now_str, term_id, term_chinese, user_email, user_name,
                action_type, field_changed, old_value, new_value, details,
            ])
        except Exception as exc:
            logger.warning("Audit Sheet mirror write failed: %s", exc)

    except Exception:
        pass
