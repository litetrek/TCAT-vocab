import os
import unicodedata
import re
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL", "vlin77@gmail.com")
SHEET_ID          = os.getenv("SHEET_ID")

# ── Column indices for Terms sheet (1-based for gspread) ──────────────────
COL = {
    "id": 1, "chinese": 2, "pinyin": 3, "pali": 4, "sanskrit": 5,
    "context": 6, "category": 7, "notes": 8,
    "trans1": 9, "trans2": 10, "trans3": 11,
    "final": 12, "status": 13, "added_by": 14, "timestamp": 15,
    "trans_known":  16, "source": 17, "trans_first": 18, "trans_second": 19,
    "trans_other1": 20, "trans_other2": 21,
    "last_modified_by": 22, "last_modified_time": 23,
    "romanization_plain": 24,
    "source_content_chinese": 25,
    "source_content_english": 26,
}

TERMS_HEADER = [
    "ID", "Chinese", "Pinyin", "Pali", "Sanskrit", "Context",
    "Category", "Notes", "Translation1", "Translation2", "Translation3",
    "Final", "Status", "AddedBy", "Timestamp",
    "TranslationKnown", "Source", "TranslationFirst", "TranslationSecond",
    "TranslationOther1", "TranslationOther2",
    "LastModifiedBy", "LastModifiedTime", "RomanizationPlain",
    "SourceContentChinese", "SourceContentEnglish",
]

SOURCE_HEADER  = ["SourceID", "SourceName", "SourceType", "Notes"]
MEMBERS_HEADER = ["Email", "Role", "AddedBy", "AddedAt", "Name", "ShortName"]

AUDIT_LOG_HEADER = [
    "AuditID", "Timestamp", "TermID", "TermChinese",
    "UserEmail", "UserName", "ActionType",
    "FieldChanged", "OldValue", "NewValue", "Details",
]

EXTRACTION_DOCUMENTS_HEADER = [
    "DocumentID", "Title", "SourceName", "ParagraphCount",
    "UploadedBy", "UploadedAt", "LastViewedIndex", "Status",
]

EXTRACTION_PARAGRAPHS_HEADER = [
    "DocumentID", "ParagraphIndex", "ChineseText", "EnglishText",
]

SOURCE_TYPES = ["Scripture", "Commentary", "Dictionary", "Encyclopedia", "Other"]
VALID_ROLES  = ("viewer", "depositor", "member", "leader", "admin")

MCOL = {"email": 1, "role": 2, "added_by": 3, "added_at": 4, "name": 5, "short_name": 6}

FIELD_LABELS = {
    "pinyin":       "Pinyin",
    "trans1":       "Translation 1",
    "trans2":       "Translation 2",
    "trans3":       "Translation 3",
    "trans_known":  "Known Translation",
    "trans_other1": "Suggested 1",
    "trans_other2": "Suggested 2",
    "sources":      "Sources",
    "context":      "Context",
    "category":     "Category",
    "notes":        "Notes",
    "source_content_chinese": "Source Content Chinese",
    "source_content_english": "Source Content English",
    "entity_type":   "Entity Type",
    "subject_field": "Subject Field",
}

VOTE_LABELS = {
    "Translation1":      "Option 1",
    "Translation2":      "Option 2",
    "Translation3":      "Option 3",
    "TranslationKnown":  "Known",
    "TranslationOther1": "Suggested 1",
    "TranslationOther2": "Suggested 2",
}

# Maps vote key → COL key (used in api_set_final)
VOTE_KEY_TO_COL_KEY = {
    "Translation1":      "trans1",
    "Translation2":      "trans2",
    "Translation3":      "trans3",
    "TranslationKnown":  "trans_known",
    "TranslationOther1": "trans_other1",
    "TranslationOther2": "trans_other2",
}


def normalize_translation(text):
    """Normalize a translation string for duplicate comparison."""
    if not text:
        return ""
    t = text.strip().lower()
    t = t.rstrip(".,;:!?'\"")
    t = re.sub(r'[-–—_]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def strip_tone_marks(text):
    """Strip Pinyin tone diacritics for plain-text search (xiūxíng → xiuxing)."""
    if not text:
        return ""
    plain = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")
    return plain.lower().replace(" ", "")
