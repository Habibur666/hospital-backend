"""
User Management Module — admin can list, view, update and activate/deactivate users.
"""
import bcrypt
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail, get_pagination_params, paginated
from app.decorators import role_required, login_required, ROLES
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity, get_jwt

users_bp = Blueprint("users", __name__)

SAFE_COLUMNS = "id, first_name, last_name, email, phone, role, is_active, last_login_at, created_at"


@users_bp.route("", methods=["POST"])
@role_required("super_admin", "hospital_admin")
def create_staff_user():
    """
    Admin-only way to create accounts for any role (doctor, receptionist,
    pharmacist, lab_technician, cashier, or another admin). Public
    self-registration (POST /auth/register) only ever creates patients —
    this is the one place staff accounts should be created from.
    """
    data = request.get_json() or {}
    required_fields = ["first_name", "last_name", "email", "password", "role"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    if data["role"] not in ROLES:
        return fail(f"role must be one of {ROLES}", 422)
    if len(data["password"]) < 8:
        return fail("Password must be at least 8 characters long", 422)

    existing = query_one("SELECT id FROM users WHERE email = %s", (data["email"],))
    if existing:
        return fail("A user with this email already exists", 409)

    password_hash = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user_id = execute(
        """
        INSERT INTO users (first_name, last_name, email, phone, password_hash, role)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (data["first_name"], data["last_name"], data["email"], data.get("phone"), password_hash, data["role"]),
    )
    log_action(get_jwt_identity(), "create_staff_user", "user", user_id, f"role={data['role']}")

    user = query_one(f"SELECT {SAFE_COLUMNS} FROM users WHERE id = %s", (user_id,))
    return ok(user, "Staff account created", 201)


@users_bp.route("", methods=["GET"])
@role_required("super_admin", "hospital_admin")
def list_users():
    page, per_page, offset = get_pagination_params()
    role_filter = request.args.get("role")
    search = request.args.get("search")

    sql = f"SELECT {SAFE_COLUMNS} FROM users WHERE 1=1"
    count_sql = "SELECT COUNT(*) AS total FROM users WHERE 1=1"
    params = []

    if role_filter:
        sql += " AND role = %s"
        count_sql += " AND role = %s"
        params.append(role_filter)

    if search:
        sql += " AND (first_name LIKE %s OR last_name LIKE %s OR email LIKE %s)"
        count_sql += " AND (first_name LIKE %s OR last_name LIKE %s OR email LIKE %s)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    total = query_one(count_sql, tuple(params))["total"]
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    rows = query_all(sql, tuple(params) + (per_page, offset))

    return paginated(rows, page, per_page, total)


@users_bp.route("/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    claims = get_jwt()
    if claims.get("role") not in ("super_admin", "hospital_admin") and str(user_id) != str(get_jwt_identity()):
        return fail("You can only view your own profile", 403)
    user = query_one(f"SELECT {SAFE_COLUMNS} FROM users WHERE id = %s", (user_id,))
    if not user:
        return fail("User not found", 404)
    return ok(user)


@users_bp.route("/<int:user_id>", methods=["PUT"])
@role_required("super_admin", "hospital_admin")
def update_user(user_id):
    data = request.get_json() or {}
    user = query_one("SELECT id FROM users WHERE id = %s", (user_id,))
    if not user:
        return fail("User not found", 404)

    fields, params = [], []
    for field in ["first_name", "last_name", "phone", "role"]:
        if field in data:
            fields.append(f"{field} = %s")
            params.append(data[field])

    if not fields:
        return fail("No valid fields to update", 422)

    params.append(user_id)
    execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", tuple(params))
    log_action(get_jwt_identity(), "update_user", "user", user_id)

    updated = query_one(f"SELECT {SAFE_COLUMNS} FROM users WHERE id = %s", (user_id,))
    return ok(updated, "User updated successfully")


@users_bp.route("/<int:user_id>/status", methods=["PATCH"])
@role_required("super_admin", "hospital_admin")
def change_status(user_id):
    data = request.get_json() or {}
    is_active = data.get("is_active")
    if is_active is None:
        return fail("'is_active' (true/false) is required", 422)

    user = query_one("SELECT id FROM users WHERE id = %s", (user_id,))
    if not user:
        return fail("User not found", 404)

    execute("UPDATE users SET is_active = %s WHERE id = %s", (1 if is_active else 0, user_id))
    log_action(get_jwt_identity(), "change_user_status", "user", user_id, f"is_active={is_active}")
    return ok(None, "User status updated")


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@role_required("super_admin")
def delete_user(user_id):
    user = query_one("SELECT id FROM users WHERE id = %s", (user_id,))
    if not user:
        return fail("User not found", 404)

    execute("DELETE FROM users WHERE id = %s", (user_id,))
    log_action(get_jwt_identity(), "delete_user", "user", user_id)
    return ok(None, "User deleted successfully")
