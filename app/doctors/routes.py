"""
Doctor Management Module — doctor profiles, availability, appointments, consultation history.
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import (
    ok, fail, get_pagination_params, paginated,
    verify_doctor_self_access,
)
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity

doctors_bp = Blueprint("doctors", __name__)

DOCTOR_SELECT = """
    SELECT d.id, d.user_id, d.department_id, d.specialty, d.qualification,
           d.experience_years, d.consultation_fee, d.created_at,
           u.first_name, u.last_name, u.email, u.phone,
           dep.name AS department_name
    FROM doctors d
    JOIN users u ON u.id = d.user_id
    LEFT JOIN departments dep ON dep.id = d.department_id
"""


@doctors_bp.route("", methods=["GET"])
@login_required
def list_doctors():
    page, per_page, offset = get_pagination_params()
    department_id = request.args.get("department_id")
    search = request.args.get("search")

    sql = DOCTOR_SELECT + " WHERE 1=1"
    count_sql = "SELECT COUNT(*) AS total FROM doctors d JOIN users u ON u.id = d.user_id WHERE 1=1"
    params = []

    if department_id:
        sql += " AND d.department_id = %s"
        count_sql += " AND d.department_id = %s"
        params.append(department_id)

    if search:
        sql += " AND (u.first_name LIKE %s OR u.last_name LIKE %s OR d.specialty LIKE %s)"
        count_sql += " AND (u.first_name LIKE %s OR u.last_name LIKE %s OR d.specialty LIKE %s)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    total = query_one(count_sql, tuple(params))["total"]
    sql += " ORDER BY d.created_at DESC LIMIT %s OFFSET %s"
    rows = query_all(sql, tuple(params) + (per_page, offset))
    return paginated(rows, page, per_page, total)


@doctors_bp.route("", methods=["POST"])
@role_required("super_admin", "hospital_admin")
def create_doctor_profile():
    """Attach doctor-specific details to an existing user account (role='doctor')."""
    data = request.get_json() or {}
    if not data.get("user_id"):
        return fail("'user_id' is required", 422)

    user = query_one("SELECT id, role FROM users WHERE id = %s", (data["user_id"],))
    if not user:
        return fail("User not found", 404)
    if user["role"] != "doctor":
        return fail("This user does not have the 'doctor' role", 422)

    existing = query_one("SELECT id FROM doctors WHERE user_id = %s", (data["user_id"],))
    if existing:
        return fail("This user already has a doctor profile", 409)

    doctor_id = execute(
        """
        INSERT INTO doctors (user_id, department_id, specialty, qualification, experience_years, consultation_fee)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (data["user_id"], data.get("department_id"), data.get("specialty"),
         data.get("qualification"), data.get("experience_years"), data.get("consultation_fee")),
    )
    log_action(get_jwt_identity(), "create_doctor_profile", "doctor", doctor_id)
    return ok(query_one(DOCTOR_SELECT + " WHERE d.id = %s", (doctor_id,)), "Doctor profile created", 201)


@doctors_bp.route("/me", methods=["GET"])
@role_required("doctor")
def get_my_doctor_profile():
    """Lets a logged-in doctor find their own doctor_id reliably, instead
    of guessing via search. Used by the frontend to gate actions like
    cancelling appointments to the doctor's own appointments only."""
    row = query_one(DOCTOR_SELECT + " WHERE d.user_id = %s", (get_jwt_identity(),))
    if not row:
        return fail("No doctor profile is linked to your account yet.", 404)
    return ok(row)


@doctors_bp.route("/<int:doctor_id>", methods=["GET"])
@login_required
def get_doctor(doctor_id):
    doctor = query_one(DOCTOR_SELECT + " WHERE d.id = %s", (doctor_id,))
    if not doctor:
        return fail("Doctor not found", 404)
    return ok(doctor)


@doctors_bp.route("/<int:doctor_id>", methods=["PUT"])
@role_required("super_admin", "hospital_admin", "doctor")
def update_doctor(doctor_id):
    data = request.get_json() or {}
    doctor = query_one("SELECT id FROM doctors WHERE id = %s", (doctor_id,))
    if not doctor:
        return fail("Doctor not found", 404)

    denied = verify_doctor_self_access(doctor_id)
    if denied:
        return denied

    fields, params = [], []
    for field in ["department_id", "specialty", "qualification", "experience_years", "consultation_fee"]:
        if field in data:
            fields.append(f"{field} = %s")
            params.append(data[field])

    if not fields:
        return fail("No valid fields to update", 422)

    params.append(doctor_id)
    execute(f"UPDATE doctors SET {', '.join(fields)} WHERE id = %s", tuple(params))
    log_action(get_jwt_identity(), "update_doctor", "doctor", doctor_id)
    return ok(query_one(DOCTOR_SELECT + " WHERE d.id = %s", (doctor_id,)), "Doctor updated")


# ---------------- Availability ----------------

@doctors_bp.route("/<int:doctor_id>/availability", methods=["GET"])
@login_required
def list_availability(doctor_id):
    rows = query_all(
        "SELECT * FROM doctor_availability WHERE doctor_id = %s ORDER BY FIELD(day_of_week,'mon','tue','wed','thu','fri','sat','sun')",
        (doctor_id,),
    )
    return ok(rows)


@doctors_bp.route("/<int:doctor_id>/availability", methods=["POST"])
@role_required("doctor", "hospital_admin", "super_admin")
def add_availability(doctor_id):
    denied = verify_doctor_self_access(doctor_id)
    if denied:
        return denied

    data = request.get_json() or {}
    required_fields = ["day_of_week", "start_time", "end_time"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    slot_id = execute(
        "INSERT INTO doctor_availability (doctor_id, day_of_week, start_time, end_time) VALUES (%s, %s, %s, %s)",
        (doctor_id, data["day_of_week"], data["start_time"], data["end_time"]),
    )
    return ok(query_one("SELECT * FROM doctor_availability WHERE id = %s", (slot_id,)), "Availability added", 201)


@doctors_bp.route("/availability/<int:slot_id>", methods=["DELETE"])
@role_required("doctor", "hospital_admin", "super_admin")
def delete_availability(slot_id):
    slot = query_one("SELECT doctor_id FROM doctor_availability WHERE id = %s", (slot_id,))
    if not slot:
        return fail("Availability slot not found", 404)
    denied = verify_doctor_self_access(slot["doctor_id"])
    if denied:
        return denied

    execute("DELETE FROM doctor_availability WHERE id = %s", (slot_id,))
    return ok(None, "Availability removed")


# ---------------- Doctor's own appointments / consultation history ----------------

@doctors_bp.route("/<int:doctor_id>/appointments", methods=["GET"])
@role_required("doctor", "hospital_admin", "super_admin", "receptionist")
def doctor_appointments(doctor_id):
    denied = verify_doctor_self_access(doctor_id)
    if denied:
        return denied

    status = request.args.get("status")
    sql = """
        SELECT a.*, p.first_name AS patient_first_name, p.last_name AS patient_last_name
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.doctor_id = %s
    """
    params = [doctor_id]
    if status:
        sql += " AND a.status = %s"
        params.append(status)
    sql += " ORDER BY a.appointment_date, a.appointment_time"
    return ok(query_all(sql, tuple(params)))


@doctors_bp.route("/<int:doctor_id>/consultations", methods=["GET"])
@role_required("doctor", "hospital_admin", "super_admin")
def doctor_consultation_history(doctor_id):
    denied = verify_doctor_self_access(doctor_id)
    if denied:
        return denied

    rows = query_all(
        """
        SELECT c.*, p.first_name AS patient_first_name, p.last_name AS patient_last_name
        FROM consultation_notes c
        JOIN patients p ON p.id = c.patient_id
        WHERE c.doctor_id = %s
        ORDER BY c.created_at DESC
        """,
        (doctor_id,),
    )
    return ok(rows)
