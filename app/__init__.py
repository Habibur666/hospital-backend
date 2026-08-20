"""
app/__init__.py

This is the "app factory" — the function that builds and configures our
Flask app. It connects the database, JWT, CORS, and registers every
module's routes (blueprints) under /api/v1/...
"""
import os
from datetime import timedelta
from decimal import Decimal
from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from app.config import Config
from app import db as db_module
from app.helpers import fail

jwt = JWTManager()


class CustomJSONProvider(DefaultJSONProvider):
    """
    PyMySQL returns MySQL TIME columns (e.g. appointment_time) as Python
    timedelta objects, and DECIMAL columns (e.g. consultation_fee,
    unit_price) as Decimal objects — neither of which Flask's default JSON
    encoder knows how to serialize. Without this, any endpoint returning a
    TIME or DECIMAL column crashes with a 500 error ("Object of type
    timedelta/Decimal is not JSON serializable").
    """

    @staticmethod
    def default(obj):
        if isinstance(obj, timedelta):
            total_seconds = int(obj.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        if isinstance(obj, Decimal):
            return float(obj)
        return DefaultJSONProvider.default(obj)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json = CustomJSONProvider(app)

    # ---- Database (PyMySQL, connected per-request) ----
    db_module.init_app(app)

    # ---- JWT ----
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = app.config["JWT_ACCESS_TOKEN_EXPIRES_MINUTES"] * 60
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = app.config["JWT_REFRESH_TOKEN_EXPIRES_DAYS"] * 86400
    jwt.init_app(app)

    # Check the token blocklist on every request (for real logout support)
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        from app.db import query_one
        row = query_one("SELECT id FROM token_blocklist WHERE jti = %s", (jwt_payload["jti"],))
        return row is not None

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return fail("Token has expired", 401)

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return fail("Invalid token", 401)

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return fail("Missing authorization token", 401)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return fail("Token has been revoked, please log in again", 401)

    # ---- CORS ----
    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)

    # ---- Register every module (blueprint) ----
    from app.auth.routes import auth_bp
    from app.users.routes import users_bp
    from app.departments.routes import departments_bp
    from app.doctors.routes import doctors_bp
    from app.patients.routes import patients_bp
    from app.appointments.routes import appointments_bp
    from app.consultations.routes import consultations_bp
    from app.prescriptions.routes import prescriptions_bp
    from app.medical_records.routes import medical_records_bp
    from app.laboratory.routes import laboratory_bp
    from app.pharmacy.routes import pharmacy_bp
    from app.inventory.routes import inventory_bp
    from app.billing.routes import billing_bp
    from app.admissions.routes import admissions_bp
    from app.emergency.routes import emergency_bp
    from app.reports.routes import reports_bp
    from app.dashboard.routes import dashboard_bp
    from app.notifications.routes import notifications_bp
    from app.audit.routes import audit_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(departments_bp, url_prefix="/api/v1/departments")
    app.register_blueprint(doctors_bp, url_prefix="/api/v1/doctors")
    app.register_blueprint(patients_bp, url_prefix="/api/v1/patients")
    app.register_blueprint(appointments_bp, url_prefix="/api/v1/appointments")
    app.register_blueprint(consultations_bp, url_prefix="/api/v1/consultations")
    app.register_blueprint(prescriptions_bp, url_prefix="/api/v1/prescriptions")
    app.register_blueprint(medical_records_bp, url_prefix="/api/v1/medical-records")
    app.register_blueprint(laboratory_bp, url_prefix="/api/v1/laboratory")
    app.register_blueprint(pharmacy_bp, url_prefix="/api/v1/pharmacy")
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")
    app.register_blueprint(billing_bp, url_prefix="/api/v1/billing")
    app.register_blueprint(admissions_bp, url_prefix="/api/v1/admissions")
    app.register_blueprint(emergency_bp, url_prefix="/api/v1/emergency")
    app.register_blueprint(reports_bp, url_prefix="/api/v1/reports")
    app.register_blueprint(dashboard_bp, url_prefix="/api/v1/dashboard")
    app.register_blueprint(notifications_bp, url_prefix="/api/v1/notifications")
    app.register_blueprint(audit_bp, url_prefix="/api/v1/audit-logs")

    # ---- Simple global error handling ----
    @app.errorhandler(404)
    def not_found(e):
        return fail("The requested endpoint does not exist", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return fail("Method not allowed on this endpoint", 405)

    @app.errorhandler(413)
    def file_too_large(e):
        return fail("File is too large. Maximum allowed size is 0.5 MB", 413)

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        # Let 404/405/413 pass through to their own handlers above
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return fail(e.description or e.name, e.code or 500)
        app.logger.exception("Unexpected error")
        return fail("An unexpected error occurred", 500)

    @app.route("/health")
    def health_check():
        return {"status": "ok", "service": "hospital-management-system"}, 200

    return app
