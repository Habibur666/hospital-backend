"""
Admission & Bed Management Module — manage beds, admit/discharge patients.
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity

admissions_bp = Blueprint("admissions", __name__)


# ---------------- Beds ----------------

@admissions_bp.route("/beds", methods=["GET"])
@login_required
def list_beds():
    status = request.args.get("status")
    sql = "SELECT * FROM beds WHERE 1=1"
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY ward_name, bed_number"
    return ok(query_all(sql, tuple(params)))


@admissions_bp.route("/beds", methods=["POST"])
@role_required("hospital_admin", "super_admin")
def create_bed():
    data = request.get_json() or {}
    if not data.get("ward_name") or not data.get("bed_number"):
        return fail("'ward_name' and 'bed_number' are required", 422)

    bed_id = execute(
        "INSERT INTO beds (ward_name, bed_number) VALUES (%s, %s)",
        (data["ward_name"], data["bed_number"]),
    )
    return ok(query_one("SELECT * FROM beds WHERE id = %s", (bed_id,)), "Bed added", 201)


# ---------------- Admissions ----------------

@admissions_bp.route("", methods=["GET"])
@role_required("doctor", "hospital_admin", "super_admin", "receptionist")
def list_admissions():
    status = request.args.get("status")
    sql = """
        SELECT a.*, p.first_name AS patient_first_name, p.last_name AS patient_last_name,
               b.ward_name, b.bed_number
        FROM admissions a
        JOIN patients p ON p.id = a.patient_id
        JOIN beds b ON b.id = a.bed_id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND a.status = %s"
        params.append(status)
    sql += " ORDER BY a.admitted_at DESC"
    return ok(query_all(sql, tuple(params)))


@admissions_bp.route("", methods=["POST"])
@role_required("doctor", "hospital_admin", "super_admin", "receptionist")
def admit_patient():
    data = request.get_json() or {}
    required_fields = ["patient_id", "bed_id"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    bed = query_one("SELECT * FROM beds WHERE id = %s", (data["bed_id"],))
    if not bed:
        return fail("Bed not found", 404)
    if bed["status"] != "available":
        return fail("Selected bed is not available", 422)

    admission_id = execute(
        "INSERT INTO admissions (patient_id, bed_id, doctor_id, reason) VALUES (%s, %s, %s, %s)",
        (data["patient_id"], data["bed_id"], data.get("doctor_id"), data.get("reason")),
    )
    execute("UPDATE beds SET status = 'occupied' WHERE id = %s", (data["bed_id"],))

    log_action(get_jwt_identity(), "admit_patient", "admission", admission_id)
    return ok(query_one("SELECT * FROM admissions WHERE id = %s", (admission_id,)), "Patient admitted", 201)


@admissions_bp.route("/<int:admission_id>/discharge", methods=["PATCH"])
@role_required("doctor", "hospital_admin", "super_admin")
def discharge_patient(admission_id):
    admission = query_one("SELECT * FROM admissions WHERE id = %s", (admission_id,))
    if not admission:
        return fail("Admission not found", 404)

    execute("UPDATE admissions SET status = 'discharged', discharged_at = NOW() WHERE id = %s", (admission_id,))
    execute("UPDATE beds SET status = 'available' WHERE id = %s", (admission["bed_id"],))

    log_action(get_jwt_identity(), "discharge_patient", "admission", admission_id)
    return ok(query_one("SELECT * FROM admissions WHERE id = %s", (admission_id,)), "Patient discharged")
