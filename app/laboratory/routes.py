"""
Laboratory Management Module — test requests, status updates, report uploads.
"""
import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, current_app
from app.db import query_all, query_one, execute
from app.helpers import ok, fail, allowed_file, get_pagination_params, paginated
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity, get_jwt

laboratory_bp = Blueprint("laboratory", __name__)


@laboratory_bp.route("", methods=["GET"])
@role_required("lab_technician", "doctor", "hospital_admin", "super_admin", "patient")
def list_tests():
    page, per_page, offset = get_pagination_params()
    status = request.args.get("status")
    patient_id = request.args.get("patient_id")

    # A "patient" must only ever see their own lab tests, no matter what
    # patient_id (if any) they pass in — force it to their own record.
    if get_jwt().get("role") == "patient":
        own_patient = query_one("SELECT id FROM patients WHERE user_id = %s", (get_jwt_identity(),))
        patient_id = own_patient["id"] if own_patient else -1  # -1 => no results if no profile yet

    sql = "SELECT * FROM lab_tests WHERE 1=1"
    count_sql = "SELECT COUNT(*) AS total FROM lab_tests WHERE 1=1"
    params = []
    for column, value in [("status", status), ("patient_id", patient_id)]:
        if value:
            sql += f" AND {column} = %s"
            count_sql += f" AND {column} = %s"
            params.append(value)

    total = query_one(count_sql, tuple(params))["total"]
    sql += " ORDER BY requested_at DESC LIMIT %s OFFSET %s"
    rows = query_all(sql, tuple(params) + (per_page, offset))
    return paginated(rows, page, per_page, total)


@laboratory_bp.route("", methods=["POST"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin")
def request_test():
    data = request.get_json() or {}
    required_fields = ["patient_id", "test_name"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    test_id = execute(
        "INSERT INTO lab_tests (patient_id, doctor_id, test_name) VALUES (%s, %s, %s)",
        (data["patient_id"], data.get("doctor_id"), data["test_name"]),
    )
    log_action(get_jwt_identity(), "request_lab_test", "lab_test", test_id)
    return ok(query_one("SELECT * FROM lab_tests WHERE id = %s", (test_id,)), "Lab test requested", 201)


@laboratory_bp.route("/<int:test_id>/status", methods=["PATCH"])
@role_required("lab_technician", "hospital_admin", "super_admin")
def update_status(test_id):
    data = request.get_json() or {}
    new_status = data.get("status")
    valid_statuses = ["requested", "in_progress", "completed", "cancelled"]
    if new_status not in valid_statuses:
        return fail(f"'status' must be one of {valid_statuses}", 422)

    test = query_one("SELECT id FROM lab_tests WHERE id = %s", (test_id,))
    if not test:
        return fail("Lab test not found", 404)

    if new_status == "completed":
        execute("UPDATE lab_tests SET status = %s, completed_at = NOW() WHERE id = %s", (new_status, test_id))
    else:
        execute("UPDATE lab_tests SET status = %s WHERE id = %s", (new_status, test_id))

    log_action(get_jwt_identity(), "update_lab_test_status", "lab_test", test_id, new_status)
    return ok(query_one("SELECT * FROM lab_tests WHERE id = %s", (test_id,)), "Status updated")


@laboratory_bp.route("/<int:test_id>/report", methods=["POST"])
@role_required("lab_technician", "hospital_admin", "super_admin")
def upload_report(test_id):
    if "file" not in request.files:
        return fail("No file was uploaded (expected form field 'file')", 422)

    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        return fail("Only PDF, PNG, and JPG files are allowed", 422)

    test = query_one("SELECT id FROM lab_tests WHERE id = %s", (test_id,))
    if not test:
        return fail("Lab test not found", 404)

    cloudinary.config(
        cloud_name=current_app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=current_app.config["CLOUDINARY_API_KEY"],
        api_secret=current_app.config["CLOUDINARY_API_SECRET"],
    )
    upload_result = cloudinary.uploader.upload(file, resource_type="auto", folder="lab_reports")

    execute(
        "UPDATE lab_tests SET report_url = %s, status = 'completed', completed_at = NOW() WHERE id = %s",
        (upload_result["secure_url"], test_id),
    )
    log_action(get_jwt_identity(), "upload_lab_report", "lab_test", test_id)
    return ok(query_one("SELECT * FROM lab_tests WHERE id = %s", (test_id,)), "Report uploaded")
