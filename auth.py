from flask import session


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
