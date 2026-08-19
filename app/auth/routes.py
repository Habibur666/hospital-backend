"""
Auth Module — register, login, logout, refresh token.
Beginner-style: everything for this module lives in one simple file.
"""
import bcrypt
from datetime import datetime, timezone
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)

from app.db import query_one, execute
from app.helpers import ok, fail
from app.decorators import ROLES
from app.audit_log import log_action

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    # 1. Basic validation (kept simple on purpose)
    required_fields = ["first_name", "last_name", "email", "password"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    # Public self-registration only ever creates PATIENT accounts.
    # Staff accounts (doctor, receptionist, pharmacist, lab_technician,
    # cashier, hospital_admin, super_admin) must be created by an existing
    # admin via POST /users — otherwise anyone could register themselves
    # as a super_admin, which would be a serious security hole.
    role = "patient"

    if len(data["password"]) < 8:
        return fail("Password must be at least 8 characters long", 422)

    # 2. Check if the email is already used
    existing_user = query_one("SELECT id FROM users WHERE email = %s", (data["email"],))
    if existing_user:
        return fail("A user with this email already exists", 409)

    # 3. Hash the password before saving (never store plain text passwords)
    password_hash = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # 4. Save the new user
    user_id = execute(
        """
        INSERT INTO users (first_name, last_name, email, phone, password_hash, role)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (data["first_name"], data["last_name"], data["email"],
         data.get("phone"), password_hash, role),
    )

    # 5. Auto-create the linked patient profile right away, so the new
    # account can immediately book appointments etc. without a separate
    # manual "register your patient profile" step.
    execute(
        "INSERT INTO patients (user_id, first_name, last_name, phone, email) VALUES (%s, %s, %s, %s, %s)",
        (user_id, data["first_name"], data["last_name"], data.get("phone"), data["email"]),
    )

    log_action(user_id, "register", "user", user_id, "New account created")

    user = query_one(
        "SELECT id, first_name, last_name, email, phone, role, is_active, created_at FROM users WHERE id = %s",
        (user_id,),
    )
    return ok(user, "User registered successfully", 201)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return fail("email and password are required", 422)

    user = query_one("SELECT * FROM users WHERE email = %s", (email,))

    if not user or not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return fail("Invalid email or password", 401)

    if not user["is_active"]:
        return fail("This account has been deactivated", 401)

    # Update last login time
    execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],))

    # Create tokens. We store role/email in the token so other modules
    # can check permissions without hitting the database every time.
    extra_claims = {"role": user["role"], "email": user["email"]}
    access_token = create_access_token(identity=str(user["id"]), additional_claims=extra_claims)
    refresh_token = create_refresh_token(identity=str(user["id"]), additional_claims=extra_claims)

    user.pop("password_hash", None)
    log_action(user["id"], "login", "user", user["id"])

    return ok({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }, "Login successful")


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = query_one("SELECT * FROM users WHERE id = %s", (user_id,))

    if not user or not user["is_active"]:
        return fail("Account no longer active", 401)

    access_token = create_access_token(
        identity=str(user["id"]),
        additional_claims={"role": user["role"], "email": user["email"]},
    )
    return ok({"access_token": access_token}, "Access token refreshed")


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    claims = get_jwt()
    jti = claims["jti"]
    user_id = get_jwt_identity()
    expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)

    execute(
        "INSERT INTO token_blocklist (jti, user_id, expires_at) VALUES (%s, %s, %s)",
        (jti, user_id, expires_at),
    )
    log_action(user_id, "logout", "user", user_id)
    return ok(None, "Logged out successfully")
