"""
Prescription Management Module — doctors write prescriptions with one or more medicine items.
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail, verify_patient_self_access, get_own_doctor_id
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity, get_jwt

prescriptions_bp = Blueprint("prescriptions", __name__)


@prescriptions_bp.route("", methods=["POST"])
@role_required("doctor")
def create_prescription():
    data = request.get_json() or {}
    required_fields = ["patient_id", "items"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    if not isinstance(data["items"], list) or len(data["items"]) == 0:
        return fail("'items' must be a non-empty list of medicines", 422)

    # A doctor can only ever write prescriptions under THEIR OWN doctor_id.
    own_doctor_id = get_own_doctor_id(get_jwt_identity())
    if not own_doctor_id:
        return fail("No doctor profile is linked to your account.", 404)

    prescription_id = execute(
        "INSERT INTO prescriptions (appointment_id, doctor_id, patient_id, notes) VALUES (%s, %s, %s, %s)",
        (data.get("appointment_id"), own_doctor_id, data["patient_id"], data.get("notes")),
    )

    for item in data["items"]:
        if not item.get("medicine_name"):
            continue
        execute(
            """
            INSERT INTO prescription_items (prescription_id, medicine_name, dosage, frequency, duration)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (prescription_id, item["medicine_name"], item.get("dosage"),
             item.get("frequency"), item.get("duration")),
        )

    log_action(get_jwt_identity(), "create_prescription", "prescription", prescription_id)

    prescription = query_one("SELECT * FROM prescriptions WHERE id = %s", (prescription_id,))
    prescription["items"] = query_all(
        "SELECT * FROM prescription_items WHERE prescription_id = %s", (prescription_id,)
    )
    return ok(prescription, "Prescription created", 201)


@prescriptions_bp.route("/<int:prescription_id>", methods=["GET"])
@role_required("doctor", "hospital_admin", "super_admin", "patient", "pharmacist")
def get_prescription(prescription_id):
    prescription = query_one("SELECT * FROM prescriptions WHERE id = %s", (prescription_id,))
    if not prescription:
        return fail("Prescription not found", 404)

    role = get_jwt().get("role")
    if role == "patient":
        denied = verify_patient_self_access(prescription["patient_id"])
        if denied:
            return denied
    elif role == "doctor":
        own_doctor_id = get_own_doctor_id(get_jwt_identity())
        if own_doctor_id != prescription["doctor_id"]:
            return fail("You can only view your own prescriptions", 403)

    prescription["items"] = query_all(
        "SELECT * FROM prescription_items WHERE prescription_id = %s", (prescription_id,)
    )
    return ok(prescription)


@prescriptions_bp.route("/patient/<int:patient_id>", methods=["GET"])
@role_required("doctor", "hospital_admin", "super_admin", "patient", "pharmacist")
def list_by_patient(patient_id):
    denied = verify_patient_self_access(patient_id)
    if denied:
        return denied
    rows = query_all(
        "SELECT * FROM prescriptions WHERE patient_id = %s ORDER BY created_at DESC", (patient_id,)
    )
    for row in rows:
        row["items"] = query_all(
            "SELECT * FROM prescription_items WHERE prescription_id = %s", (row["id"],)
        )
    return ok(rows)
