"""
helpers.py

Small shared helper functions used across every module, so responses
and pagination look the same everywhere in the API.
"""
from flask import jsonify, request


def ok(data=None, message="Success", status_code=200, meta=None):
    """Standard success response."""
    body = {"success": True, "message": message, "data": data}
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status_code


def fail(message="Something went wrong", status_code=400, errors=None):
    """Standard error response."""
    return jsonify({"success": False, "message": message, "errors": errors}), status_code


def get_pagination_params():
    """Read ?page= and ?per_page= from the query string with safe defaults."""
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = min(max(int(request.args.get("per_page", 10)), 1), 100)
    except ValueError:
        per_page = 10
    offset = (page - 1) * per_page
    return page, per_page, offset


def paginated(items, page, per_page, total, message="Success"):
    total_pages = (total + per_page - 1) // per_page if per_page else 0
    return ok(
        data=items,
        message=message,
        meta={
            "page": page,
            "per_page": per_page,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    )


def allowed_file(filename, allowed_extensions={"pdf", "png", "jpg", "jpeg"}):
    """Check a filename has one of the allowed extensions."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def get_own_patient_id(user_id):
    """Return the patients.id linked to this user_id, or None if not registered yet."""
    from app.db import query_one
    row = query_one("SELECT id FROM patients WHERE user_id = %s", (user_id,))
    return row["id"] if row else None


def get_own_doctor_id(user_id):
    """Return the doctors.id linked to this user_id, or None if no doctor profile yet."""
    from app.db import query_one
    row = query_one("SELECT id FROM doctors WHERE user_id = %s", (user_id,))
    return row["id"] if row else None


def verify_patient_self_access(requested_patient_id):
    """
    Some endpoints (consultation notes, prescriptions, medical records, lab
    tests) allow the "patient" role to view records, since patients should
    be able to see their own history. But a patient must only ever see
    THEIR OWN records — never another patient's, just by changing the ID
    in the URL.

    Call this after @role_required(..., "patient") on any such endpoint.
    Returns None if access is allowed, or a Flask response (403) to return
    immediately if a patient is trying to access someone else's records.
    """
    from flask_jwt_extended import get_jwt, get_jwt_identity

    claims = get_jwt()
    if claims.get("role") != "patient":
        return None  # only patients need this extra check

    own_id = get_own_patient_id(get_jwt_identity())
    if own_id is None or str(own_id) != str(requested_patient_id):
        return fail("You can only access your own records", 403)
    return None


def verify_doctor_self_access(requested_doctor_id):
    """
    Same idea as verify_patient_self_access, but for doctors managing their
    own profile/availability/appointments — a doctor must never be able to
    edit or view another doctor's data just by changing the ID in the URL.
    Admins are never restricted by this check.

    Call this after @role_required(..., "doctor") on any such endpoint.
    """
    from flask_jwt_extended import get_jwt, get_jwt_identity

    claims = get_jwt()
    if claims.get("role") != "doctor":
        return None  # only doctors need this extra check

    own_id = get_own_doctor_id(get_jwt_identity())
    if own_id is None or str(own_id) != str(requested_doctor_id):
        return fail("You can only access your own doctor profile", 403)
    return None
