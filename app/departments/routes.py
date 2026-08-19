"""
Department Management Module — simple CRUD for hospital departments.
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity

departments_bp = Blueprint("departments", __name__)


@departments_bp.route("", methods=["GET"])
@login_required
def list_departments():
    rows = query_all("SELECT * FROM departments ORDER BY name")
    return ok(rows)


@departments_bp.route("", methods=["POST"])
@role_required("super_admin", "hospital_admin")
def create_department():
    data = request.get_json() or {}
    if not data.get("name"):
        return fail("'name' is required", 422)

    existing = query_one("SELECT id FROM departments WHERE name = %s", (data["name"],))
    if existing:
        return fail("A department with this name already exists", 409)

    dept_id = execute(
        "INSERT INTO departments (name, description) VALUES (%s, %s)",
        (data["name"], data.get("description")),
    )
    log_action(get_jwt_identity(), "create_department", "department", dept_id)
    return ok(query_one("SELECT * FROM departments WHERE id = %s", (dept_id,)), "Department created", 201)


@departments_bp.route("/<int:dept_id>", methods=["GET"])
@login_required
def get_department(dept_id):
    dept = query_one("SELECT * FROM departments WHERE id = %s", (dept_id,))
    if not dept:
        return fail("Department not found", 404)
    return ok(dept)


@departments_bp.route("/<int:dept_id>", methods=["PUT"])
@role_required("super_admin", "hospital_admin")
def update_department(dept_id):
    data = request.get_json() or {}
    dept = query_one("SELECT id FROM departments WHERE id = %s", (dept_id,))
    if not dept:
        return fail("Department not found", 404)

    fields, params = [], []
    for field in ["name", "description"]:
        if field in data:
            fields.append(f"{field} = %s")
            params.append(data[field])

    if not fields:
        return fail("No valid fields to update", 422)

    params.append(dept_id)
    execute(f"UPDATE departments SET {', '.join(fields)} WHERE id = %s", tuple(params))
    log_action(get_jwt_identity(), "update_department", "department", dept_id)
    return ok(query_one("SELECT * FROM departments WHERE id = %s", (dept_id,)), "Department updated")


@departments_bp.route("/<int:dept_id>", methods=["DELETE"])
@role_required("super_admin", "hospital_admin")
def delete_department(dept_id):
    dept = query_one("SELECT id FROM departments WHERE id = %s", (dept_id,))
    if not dept:
        return fail("Department not found", 404)

    execute("DELETE FROM departments WHERE id = %s", (dept_id,))
    log_action(get_jwt_identity(), "delete_department", "department", dept_id)
    return ok(None, "Department deleted")
