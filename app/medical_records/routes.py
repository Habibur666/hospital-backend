"""
Medical Records Module — upload patient reports (PDF/PNG/JPG) to Cloudinary
and store the file metadata (URL, type, uploader) in the database.
"""
import os
import cloudinary
import cloudinary.uploader
from flask import Blueprint, request, current_app
from app.db import query_all, query_one, execute
from app.helpers import ok, fail, allowed_file, verify_patient_self_access, get_own_patient_id
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity, get_jwt

medical_records_bp = Blueprint("medical_records", __name__)


def _configure_cloudinary():
    cloudinary.config(
        cloud_name=current_app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=current_app.config["CLOUDINARY_API_KEY"],
        api_secret=current_app.config["CLOUDINARY_API_SECRET"],
    )


@medical_records_bp.route("", methods=["POST"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin", "lab_technician", "patient")
def upload_medical_record():
    if "file" not in request.files:
        return fail("No file was uploaded (expected form field 'file')", 422)

    file = request.files["file"]
    patient_id = request.form.get("patient_id")
    title = request.form.get("title", file.filename)

    # A patient can only ever upload files under THEIR OWN patient_id.
    if get_jwt().get("role") == "patient":
        own_patient_id = get_own_patient_id(get_jwt_identity())
        if not own_patient_id:
            return fail("No patient profile is linked to your account yet.", 404)
        patient_id = own_patient_id

    if not patient_id:
        return fail("'patient_id' is required", 422)

    if file.filename == "" or not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        return fail("Only PDF, PNG, and JPG files are allowed", 422)

    _configure_cloudinary()
    upload_result = cloudinary.uploader.upload(file, resource_type="auto", folder="medical_records")

    file_type = file.filename.rsplit(".", 1)[1].lower()
    record_id = execute(
        """
        INSERT INTO medical_records (patient_id, title, file_url, file_type, uploaded_by)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (patient_id, title, upload_result["secure_url"], file_type, get_jwt_identity()),
    )

    log_action(get_jwt_identity(), "upload_medical_record", "medical_record", record_id)
    return ok(query_one("SELECT * FROM medical_records WHERE id = %s", (record_id,)), "File uploaded", 201)


@medical_records_bp.route("/patient/<int:patient_id>", methods=["GET"])
@role_required("doctor", "receptionist", "hospital_admin", "super_admin", "lab_technician", "patient")
def list_by_patient(patient_id):
    denied = verify_patient_self_access(patient_id)
    if denied:
        return denied
    rows = query_all(
        "SELECT * FROM medical_records WHERE patient_id = %s ORDER BY created_at DESC", (patient_id,)
    )
    return ok(rows)


@medical_records_bp.route("/<int:record_id>", methods=["DELETE"])
@role_required("hospital_admin", "super_admin")
def delete_record(record_id):
    record = query_one("SELECT id FROM medical_records WHERE id = %s", (record_id,))
    if not record:
        return fail("Record not found", 404)
    execute("DELETE FROM medical_records WHERE id = %s", (record_id,))
    log_action(get_jwt_identity(), "delete_medical_record", "medical_record", record_id)
    return ok(None, "Record deleted")
