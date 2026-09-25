"""
Appointment Management Module — book, cancel, reschedule, approve, reject, queue.
"""
from flask import Blueprint, request
from pymysql.err import IntegrityError
from app.db import query_all, query_one, execute
from app.helpers import (
    ok, fail, get_pagination_params, paginated,
    get_own_patient_id, get_own_doctor_id,
)
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity, get_jwt

appointments_bp = Blueprint("appointments", __name__)


@appointments_bp.route("", methods=["GET"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin", "patient")
def list_appointments():
    page, per_page, offset = get_pagination_params()
    status = request.args.get("status")
    doctor_id = request.args.get("doctor_id")
    patient_id = request.args.get("patient_id")
    date = request.args.get("date")

    role = get_jwt().get("role")
    user_id = get_jwt_identity()

    # A patient must only ever see their OWN appointments, no matter what
    # patient_id (if any) they pass in — force it to their own record.
    if role == "patient":
        patient_id = get_own_patient_id(user_id) or -1
    # Likewise a doctor only sees appointments booked with them.
    elif role == "doctor":
        doctor_id = get_own_doctor_id(user_id) or -1

    sql = """
        SELECT a.*, p.first_name AS patient_first_name, p.last_name AS patient_last_name
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE 1=1
    """
    count_sql = "SELECT COUNT(*) AS total FROM appointments WHERE 1=1"
    params = []

    for column, value in [("doctor_id", doctor_id), ("patient_id", patient_id),
                           ("status", status), ("appointment_date", date)]:
        if value:
            sql += f" AND a.{column} = %s"
            count_sql += f" AND {column} = %s"
            params.append(value)

    total = query_one(count_sql, tuple(params))["total"]
    sql += " ORDER BY a.appointment_date DESC, a.appointment_time LIMIT %s OFFSET %s"
    rows = query_all(sql, tuple(params) + (per_page, offset))
    return paginated(rows, page, per_page, total)


@appointments_bp.route("", methods=["POST"])
@role_required("receptionist", "patient", "hospital_admin", "super_admin")
def book_appointment():
    data = request.get_json() or {}
    required_fields = ["patient_id", "doctor_id", "appointment_date", "appointment_time"]
    # A patient can only ever book for THEMSELVES — fill in their own
    # patient_id here, BEFORE the required-fields check below, so a
    # patient never needs to (and can't be tricked into) supplying someone
    # else's patient_id.
    if get_jwt().get("role") == "patient":
        own_patient_id = get_own_patient_id(get_jwt_identity())
        if not own_patient_id:
            return fail("No patient profile is linked to your account yet.", 404)
        data["patient_id"] = own_patient_id

    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    # Work out the next queue number for that doctor on that day
    row = query_one(
        "SELECT COUNT(*) AS cnt FROM appointments WHERE doctor_id = %s AND appointment_date = %s",
        (data["doctor_id"], data["appointment_date"]),
    )
    queue_number = row["cnt"] + 1

    try:
        appointment_id = execute(
            """
            INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, reason, queue_number)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (data["patient_id"], data["doctor_id"], data["appointment_date"],
             data["appointment_time"], data.get("reason"), queue_number),
        )
    except IntegrityError:
        # The database itself rejected this — someone else booked this exact
        # doctor + date + time a moment ago (see the unique index on
        # active_slot_key in the appointments table). This is what actually
        # prevents two people double-booking the same slot, even if both
        # requests land at the same instant.
        return fail("This time slot was just booked by someone else. Please pick a different time.", 409)

    log_action(get_jwt_identity(), "book_appointment", "appointment", appointment_id)
    return ok(query_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,)), "Appointment booked", 201)


def _verify_appointment_owner(appt):
    """
    Returns None if the current user is allowed to act on this appointment,
    or a Flask response (403) to return immediately otherwise.
    Staff (receptionist/hospital_admin/super_admin) can act on any
    appointment; a patient or doctor may only act on their own.
    """
    role = get_jwt().get("role")
    user_id = get_jwt_identity()

    if role == "patient":
        own_id = get_own_patient_id(user_id)
        if own_id is None or own_id != appt["patient_id"]:
            return fail("You can only manage your own appointments", 403)
    elif role == "doctor":
        own_id = get_own_doctor_id(user_id)
        if own_id is None or own_id != appt["doctor_id"]:
            return fail("You can only manage your own appointments", 403)
    return None


@appointments_bp.route("/<int:appointment_id>", methods=["GET"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin", "patient")
def get_appointment(appointment_id):
    appt = query_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,))
    if not appt:
        return fail("Appointment not found", 404)
    denied = _verify_appointment_owner(appt)
    if denied:
        return denied
    return ok(appt)


def _update_status(appointment_id, new_status):
    appt = query_one("SELECT id FROM appointments WHERE id = %s", (appointment_id,))
    if not appt:
        return None
    execute("UPDATE appointments SET status = %s WHERE id = %s", (new_status, appointment_id))
    return query_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,))


@appointments_bp.route("/<int:appointment_id>/approve", methods=["PATCH"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin")
def approve_appointment(appointment_id):
    appt = query_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,))
    if not appt:
        return fail("Appointment not found", 404)
    denied = _verify_appointment_owner(appt)
    if denied:
        return denied
    appt = _update_status(appointment_id, "approved")
    log_action(get_jwt_identity(), "approve_appointment", "appointment", appointment_id)
    return ok(appt, "Appointment approved")


@appointments_bp.route("/<int:appointment_id>/reject", methods=["PATCH"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin")
def reject_appointment(appointment_id):
    appt = query_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,))
    if not appt:
        return fail("Appointment not found", 404)
    denied = _verify_appointment_owner(appt)
    if denied:
        return denied
    appt = _update_status(appointment_id, "rejected")
    log_action(get_jwt_identity(), "reject_appointment", "appointment", appointment_id)
    return ok(appt, "Appointment rejected")


@appointments_bp.route("/<int:appointment_id>/cancel", methods=["PATCH"])
@role_required("receptionist", "hospital_admin", "super_admin", "doctor", "patient")
def cancel_appointment(appointment_id):
    appt = query_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,))
    if not appt:
        return fail("Appointment not found", 404)
    denied = _verify_appointment_owner(appt)
    if denied:
        return denied
    appt = _update_status(appointment_id, "cancelled")
    log_action(get_jwt_identity(), "cancel_appointment", "appointment", appointment_id)
    return ok(appt, "Appointment cancelled")


@appointments_bp.route("/<int:appointment_id>/reschedule", methods=["PATCH"])
@role_required("receptionist", "hospital_admin", "super_admin", "patient")
def reschedule_appointment(appointment_id):
    data = request.get_json() or {}
    if not data.get("appointment_date") or not data.get("appointment_time"):
        return fail("'appointment_date' and 'appointment_time' are required", 422)

    appt = query_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,))
    if not appt:
        return fail("Appointment not found", 404)
    denied = _verify_appointment_owner(appt)
    if denied:
        return denied

    try:
        execute(
            "UPDATE appointments SET appointment_date = %s, appointment_time = %s, status = 'rescheduled' WHERE id = %s",
            (data["appointment_date"], data["appointment_time"], appointment_id),
        )
    except IntegrityError:
        return fail("That time slot is already taken for this doctor. Please pick a different time.", 409)

    log_action(get_jwt_identity(), "reschedule_appointment", "appointment", appointment_id)
    return ok(query_one("SELECT * FROM appointments WHERE id = %s", (appointment_id,)), "Appointment rescheduled")


@appointments_bp.route("/queue", methods=["GET"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin")
def todays_queue():
    """Today's appointment queue for a given doctor, ordered by queue number."""
    doctor_id = request.args.get("doctor_id")
    if not doctor_id:
        return fail("'doctor_id' query param is required", 422)

    rows = query_all(
        """
        SELECT a.*, p.first_name AS patient_first_name, p.last_name AS patient_last_name
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.doctor_id = %s AND a.appointment_date = CURDATE()
        ORDER BY a.queue_number
        """,
        (doctor_id,),
    )
    return ok(rows)
