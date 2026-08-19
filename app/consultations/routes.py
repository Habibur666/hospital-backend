"""
Consultation Notes Module — doctors record symptoms, diagnosis, and notes
for a patient appointment.
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail, verify_patient_self_access, get_own_doctor_id
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity, get_jwt

consultations_bp = Blueprint("consultations", __name__)


@consultations_bp.route("", methods=["POST"])
@role_required("doctor")
def create_consultation_note():
    data = request.get_json() or {}
    required_fields = ["appointment_id", "patient_id"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    # A doctor can only ever write notes under THEIR OWN doctor_id —
    # override whatever was sent so this can't be spoofed.
    own_doctor_id = get_own_doctor_id(get_jwt_identity())
    if not own_doctor_id:
        return fail("No doctor profile is linked to your account.", 404)

    note_id = execute(
        """
        INSERT INTO consultation_notes (appointment_id, doctor_id, patient_id, symptoms, diagnosis, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (data["appointment_id"], own_doctor_id, data["patient_id"],
         data.get("symptoms"), data.get("diagnosis"), data.get("notes")),
    )
    # Mark the appointment as completed once notes are written
    execute("UPDATE appointments SET status = 'completed' WHERE id = %s", (data["appointment_id"],))

    log_action(get_jwt_identity(), "create_consultation_note", "consultation_note", note_id)
    return ok(query_one("SELECT * FROM consultation_notes WHERE id = %s", (note_id,)), "Consultation note saved", 201)


@consultations_bp.route("/patient/<int:patient_id>", methods=["GET"])
@role_required("doctor", "hospital_admin", "super_admin", "patient")
def list_by_patient(patient_id):
    denied = verify_patient_self_access(patient_id)
    if denied:
        return denied
    rows = query_all(
        "SELECT * FROM consultation_notes WHERE patient_id = %s ORDER BY created_at DESC",
        (patient_id,),
    )
    return ok(rows)


@consultations_bp.route("/<int:note_id>", methods=["GET"])
@role_required("doctor", "hospital_admin", "super_admin", "patient")
def get_consultation_note(note_id):
    note = query_one("SELECT * FROM consultation_notes WHERE id = %s", (note_id,))
    if not note:
        return fail("Consultation note not found", 404)

    role = get_jwt().get("role")
    if role == "patient":
        denied = verify_patient_self_access(note["patient_id"])
        if denied:
            return denied
    elif role == "doctor":
        own_doctor_id = get_own_doctor_id(get_jwt_identity())
        if own_doctor_id != note["doctor_id"]:
            return fail("You can only view your own consultation notes", 403)

    return ok(note)
