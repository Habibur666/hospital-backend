"""
Notifications Module — simple in-app notifications + a mock "send email" function.
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail
from app.decorators import login_required, role_required
from flask_jwt_extended import get_jwt_identity

notifications_bp = Blueprint("notifications", __name__)


def send_mock_email(to_email, subject, message):
    """
    This is a MOCK email sender — it does not actually send an email.
    In a real system this would call an email provider (SendGrid, SES, etc).
    For now we just print it, which is enough for development/testing.
    """
    print(f"[MOCK EMAIL] To: {to_email} | Subject: {subject} | Message: {message}")
    return True


@notifications_bp.route("", methods=["GET"])
@login_required
def list_my_notifications():
    user_id = get_jwt_identity()
    rows = query_all(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
    )
    return ok(rows)


@notifications_bp.route("", methods=["POST"])
@role_required("hospital_admin", "super_admin", "receptionist", "doctor")
def create_notification():
    data = request.get_json() or {}
    required_fields = ["user_id", "title", "message"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    notif_id = execute(
        "INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s)",
        (data["user_id"], data["title"], data["message"]),
    )

    # Also "send" a mock email if the user has one on file
    user = query_one("SELECT email FROM users WHERE id = %s", (data["user_id"],))
    if user and user.get("email"):
        send_mock_email(user["email"], data["title"], data["message"])

    return ok(query_one("SELECT * FROM notifications WHERE id = %s", (notif_id,)), "Notification sent", 201)


@notifications_bp.route("/<int:notif_id>/read", methods=["PATCH"])
@login_required
def mark_as_read(notif_id):
    notif = query_one("SELECT user_id FROM notifications WHERE id = %s", (notif_id,))
    if not notif:
        return fail("Notification not found", 404)
    if str(notif["user_id"]) != str(get_jwt_identity()):
        return fail("You can only mark your own notifications as read", 403)

    execute("UPDATE notifications SET is_read = 1 WHERE id = %s", (notif_id,))
    return ok(None, "Notification marked as read")
