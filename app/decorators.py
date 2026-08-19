"""
decorators.py

Simple decorators for login checks and role-based access control (RBAC).
Put @login_required or @role_required("doctor", "hospital_admin") on top
of any route function to protect it.
"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

# All roles allowed in the system
ROLES = [
    "super_admin",
    "hospital_admin",
    "doctor",
    "receptionist",
    "pharmacist",
    "lab_technician",
    "cashier",
    "patient",
]


def login_required(fn):
    """Just check that the request has a valid JWT access token."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception:
            return jsonify({"success": False, "message": "A valid access token is required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def role_required(*allowed_roles):
    """Check that the logged-in user has one of the allowed roles.

    Example:
        @role_required("doctor", "hospital_admin")
        def some_view():
            ...
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception:
                return jsonify({"success": False, "message": "A valid access token is required"}), 401

            claims = get_jwt()
            user_role = claims.get("role")

            if user_role not in allowed_roles:
                return jsonify({
                    "success": False,
                    "message": f"Role '{user_role}' is not allowed to access this resource"
                }), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator
