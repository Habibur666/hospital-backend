"""
audit.py

One simple function that every module can call to record who did what.
Keeps module 19 (Audit Logs) working automatically as other modules
create/update/delete important data.
"""
from flask import request
from app.db import execute


def log_action(user_id, action, entity_type=None, entity_id=None, details=None):
    try:
        execute(
            """
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, action, entity_type, str(entity_id) if entity_id else None,
             details, request.remote_addr),
        )
    except Exception:
        # Auditing must never break the main request
        pass
