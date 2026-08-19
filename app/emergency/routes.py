"""
Emergency Patients Module — quick intake and status tracking for walk-in
emergency cases (not yet registered as regular patients).
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail
from app.decorators import role_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity

emergency_bp = Blueprint("emergency", __name__)


@emergency_bp.route("", methods=["GET"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin")
def list_emergency_patients():
    status = request.args.get("status")
    sql = "SELECT * FROM emergency_patients WHERE 1=1"
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY FIELD(severity,'critical','high','medium','low'), created_at"
    return ok(query_all(sql, tuple(params)))


@emergency_bp.route("", methods=["POST"])
@role_required("receptionist", "doctor", "hospital_admin", "super_admin")
def register_emergency_patient():
    data = request.get_json() or {}
    if not data.get("full_name"):
        return fail("'full_name' is required", 422)

    patient_id = execute(
        """
        INSERT INTO emergency_patients (full_name, age, gender, condition_note, severity, brought_by)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (data["full_name"], data.get("age"), data.get("gender"),
         data.get("condition_note"), data.get("severity", "medium"), data.get("brought_by")),
    )
    log_action(get_jwt_identity(), "register_emergency_patient", "emergency_patient", patient_id)
    return ok(query_one("SELECT * FROM emergency_patients WHERE id = %s", (patient_id,)), "Emergency patient registered", 201)


@emergency_bp.route("/<int:patient_id>/status", methods=["PATCH"])
@role_required("doctor", "hospital_admin", "super_admin")
def update_status(patient_id):
    data = request.get_json() or {}
    new_status = data.get("status")
    valid_statuses = ["waiting", "in_treatment", "admitted", "discharged"]
    if new_status not in valid_statuses:
        return fail(f"'status' must be one of {valid_statuses}", 422)

    patient = query_one("SELECT id FROM emergency_patients WHERE id = %s", (patient_id,))
    if not patient:
        return fail("Emergency patient not found", 404)

    execute("UPDATE emergency_patients SET status = %s WHERE id = %s", (new_status, patient_id))
    log_action(get_jwt_identity(), "update_emergency_status", "emergency_patient", patient_id, new_status)
    return ok(query_one("SELECT * FROM emergency_patients WHERE id = %s", (patient_id,)), "Status updated")
