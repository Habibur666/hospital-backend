"""
Patient Management Module — register patients, update profile, medical
history, allergies, emergency contact, insurance.
(File uploads for reports are handled in the Medical Records module.)
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import (
    ok, fail, get_pagination_params, paginated,
    get_own_patient_id, verify_patient_self_access,
)
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity, get_jwt

patients_bp = Blueprint("patients", __name__)


@patients_bp.route("", methods=["GET"])
@role_required("super_admin", "hospital_admin", "receptionist", "doctor", "cashier", "pharmacist")
def list_patients():
    page, per_page, offset = get_pagination_params()
    search = request.args.get("search")

    sql = "SELECT * FROM patients WHERE 1=1"
    count_sql = "SELECT COUNT(*) AS total FROM patients WHERE 1=1"
    params = []

    if search:
        sql += " AND (first_name LIKE %s OR last_name LIKE %s OR phone LIKE %s)"
        count_sql += " AND (first_name LIKE %s OR last_name LIKE %s OR phone LIKE %s)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    total = query_one(count_sql, tuple(params))["total"]
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    rows = query_all(sql, tuple(params) + (per_page, offset))
    return paginated(rows, page, per_page, total)


@patients_bp.route("/me", methods=["GET"])
@role_required("patient")
def get_my_patient_profile():
    """
    Lets a logged-in patient find their own patient_id without needing
    access to the full patient list (which is restricted to staff roles).
    Used by the frontend to auto-fill forms like booking an appointment.
    """
    row = query_one("SELECT * FROM patients WHERE user_id = %s", (get_jwt_identity(),))
    if not row:
        return fail("No patient profile is linked to your account yet.", 404)
    return ok(row)


@patients_bp.route("", methods=["POST"])
@role_required("super_admin", "hospital_admin", "receptionist", "patient")
def register_patient():
    data = request.get_json() or {}
    required_fields = ["first_name", "last_name"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    user_id = data.get("user_id")

    # A patient can only ever create a profile linked to THEIR OWN account
    # (never someone else's user_id), and only one profile per account.
    if get_jwt().get("role") == "patient":
        user_id = get_jwt_identity()
        if get_own_patient_id(user_id) is not None:
            return fail("You already have a patient profile.", 409)

    patient_id = execute(
        """
        INSERT INTO patients (
            user_id, first_name, last_name, date_of_birth, gender, phone, email, address,
            blood_group, allergies, medical_history, emergency_contact_name,
            emergency_contact_phone, insurance_provider, insurance_policy_no
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            user_id, data["first_name"], data["last_name"], data.get("date_of_birth"),
            data.get("gender"), data.get("phone"), data.get("email"), data.get("address"),
            data.get("blood_group"), data.get("allergies"), data.get("medical_history"),
            data.get("emergency_contact_name"), data.get("emergency_contact_phone"),
            data.get("insurance_provider"), data.get("insurance_policy_no"),
        ),
    )
    log_action(get_jwt_identity(), "register_patient", "patient", patient_id)
    return ok(query_one("SELECT * FROM patients WHERE id = %s", (patient_id,)), "Patient registered", 201)


@patients_bp.route("/<int:patient_id>", methods=["GET"])
@role_required("super_admin", "hospital_admin", "receptionist", "doctor", "cashier", "pharmacist", "patient")
def get_patient(patient_id):
    denied = verify_patient_self_access(patient_id)
    if denied:
        return denied
    patient = query_one("SELECT * FROM patients WHERE id = %s", (patient_id,))
    if not patient:
        return fail("Patient not found", 404)
    return ok(patient)


@patients_bp.route("/<int:patient_id>", methods=["PUT"])
@role_required("super_admin", "hospital_admin", "receptionist", "patient")
def update_patient(patient_id):
    denied = verify_patient_self_access(patient_id)
    if denied:
        return denied

    data = request.get_json() or {}
    patient = query_one("SELECT id FROM patients WHERE id = %s", (patient_id,))
    if not patient:
        return fail("Patient not found", 404)

    editable_fields = [
        "first_name", "last_name", "date_of_birth", "gender", "phone", "email", "address",
        "blood_group", "allergies", "medical_history", "emergency_contact_name",
        "emergency_contact_phone", "insurance_provider", "insurance_policy_no",
    ]
    fields, params = [], []
    for field in editable_fields:
        if field in data:
            fields.append(f"{field} = %s")
            params.append(data[field])

    if not fields:
        return fail("No valid fields to update", 422)

    params.append(patient_id)
    execute(f"UPDATE patients SET {', '.join(fields)} WHERE id = %s", tuple(params))
    log_action(get_jwt_identity(), "update_patient", "patient", patient_id)
    return ok(query_one("SELECT * FROM patients WHERE id = %s", (patient_id,)), "Patient updated")


@patients_bp.route("/<int:patient_id>", methods=["DELETE"])
@role_required("super_admin", "hospital_admin")
def delete_patient(patient_id):
    patient = query_one("SELECT id FROM patients WHERE id = %s", (patient_id,))
    if not patient:
        return fail("Patient not found", 404)

    execute("DELETE FROM patients WHERE id = %s", (patient_id,))
    log_action(get_jwt_identity(), "delete_patient", "patient", patient_id)
    return ok(None, "Patient deleted")


@patients_bp.route("/<int:patient_id>/medical-summary", methods=["GET"])
@role_required("super_admin", "hospital_admin", "doctor", "patient")
def patient_medical_summary(patient_id):
    """Quick combined view: patient info + recent appointments + prescriptions + lab tests."""
    denied = verify_patient_self_access(patient_id)
    if denied:
        return denied

    patient = query_one("SELECT * FROM patients WHERE id = %s", (patient_id,))
    if not patient:
        return fail("Patient not found", 404)

    appointments = query_all(
        "SELECT * FROM appointments WHERE patient_id = %s ORDER BY appointment_date DESC LIMIT 5",
        (patient_id,),
    )
    prescriptions = query_all(
        "SELECT * FROM prescriptions WHERE patient_id = %s ORDER BY created_at DESC LIMIT 5",
        (patient_id,),
    )
    lab_tests = query_all(
        "SELECT * FROM lab_tests WHERE patient_id = %s ORDER BY requested_at DESC LIMIT 5",
        (patient_id,),
    )
    return ok({
        "patient": patient,
        "recent_appointments": appointments,
        "recent_prescriptions": prescriptions,
        "recent_lab_tests": lab_tests,
    })
