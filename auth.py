import os
from flask import session

_ROLE_ORDER = ["viewer", "depositor", "member", "leader", "admin"]

TRANSLATION_MODULE_MIN_ROLE = os.environ.get("TRANSLATION_MIN_ROLE", "admin")


def can_access_translation_module(user_role: str) -> bool:
    """Return True if user_role meets the minimum role required for the translation module."""
    try:
        return _ROLE_ORDER.index(user_role) >= _ROLE_ORDER.index(TRANSLATION_MODULE_MIN_ROLE)
    except ValueError:
        return False


def is_logged_in():
    return "user_email" in session


def is_admin():
    return session.get("user_role") == "admin"


def is_leader():
    return session.get("user_role") in ("leader", "admin")


def can_create_term():
    return session.get("user_role") in ("depositor", "member", "leader", "admin")


def can_edit_existing():
    return session.get("user_role") in ("member", "leader", "admin")
