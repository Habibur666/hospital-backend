"""
Dashboard Analytics Module — quick "today" numbers for the admin home screen.
"""
from flask import Blueprint
from app.db import query_all, query_one
from app.helpers import ok
from app.decorators import role_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/summary", methods=["GET"])
@role_required("hospital_admin", "super_admin")
def dashboard_summary():
    todays_appointments = query_one(
        "SELECT COUNT(*) AS total FROM appointments WHERE appointment_date = CURDATE()"
    )["total"]

    todays_patients = query_one(
        "SELECT COUNT(*) AS total FROM patients WHERE DATE(created_at) = CURDATE()"
    )["total"]

    todays_revenue = query_one(
        "SELECT COALESCE(SUM(total_amount), 0) AS total FROM invoices WHERE status = 'paid' AND DATE(created_at) = CURDATE()"
    )["total"]

    pending_appointments = query_one(
        "SELECT COUNT(*) AS total FROM appointments WHERE status = 'pending'"
    )["total"]

    return ok({
        "todays_appointments": todays_appointments,
        "todays_new_patients": todays_patients,
        "todays_revenue": float(todays_revenue),
        "pending_appointments": pending_appointments,
    })


@dashboard_bp.route("/monthly-chart", methods=["GET"])
@role_required("hospital_admin", "super_admin")
def monthly_chart():
    """Revenue and appointment counts for the last 6 months, for charting."""
    revenue_by_month = query_all(
        """
        SELECT DATE_FORMAT(created_at, '%%Y-%%m') AS month, SUM(total_amount) AS revenue
        FROM invoices
        WHERE status = 'paid' AND created_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY month
        ORDER BY month
        """
    )
    appointments_by_month = query_all(
        """
        SELECT DATE_FORMAT(appointment_date, '%%Y-%%m') AS month, COUNT(*) AS total
        FROM appointments
        WHERE appointment_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY month
        ORDER BY month
        """
    )
    return ok({"revenue_by_month": revenue_by_month, "appointments_by_month": appointments_by_month})


@dashboard_bp.route("/department-stats", methods=["GET"])
@role_required("hospital_admin", "super_admin")
def department_stats():
    rows = query_all(
        """
        SELECT dep.name AS department, COUNT(DISTINCT d.id) AS doctor_count,
               COUNT(a.id) AS appointment_count
        FROM departments dep
        LEFT JOIN doctors d ON d.department_id = dep.id
        LEFT JOIN appointments a ON a.doctor_id = d.id
        GROUP BY dep.id
        ORDER BY appointment_count DESC
        """
    )
    return ok(rows)
