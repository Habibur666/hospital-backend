"""
Reports Module — revenue, appointment stats, patient stats, pharmacy sales,
doctor performance. Each endpoint accepts optional ?start_date=&end_date=.
"""
from flask import Blueprint, request
from app.db import query_all, query_one
from app.helpers import ok
from app.decorators import role_required

reports_bp = Blueprint("reports", __name__)


def _date_range():
    start_date = request.args.get("start_date", "1970-01-01")
    end_date = request.args.get("end_date", "2999-12-31")
    return start_date, end_date


@reports_bp.route("/revenue", methods=["GET"])
@role_required("hospital_admin", "super_admin", "cashier")
def revenue_report():
    start_date, end_date = _date_range()
    summary = query_one(
        """
        SELECT COALESCE(SUM(total_amount), 0) AS total_revenue,
               COUNT(*) AS invoice_count
        FROM invoices
        WHERE status = 'paid' AND DATE(created_at) BETWEEN %s AND %s
        """,
        (start_date, end_date),
    )
    daily = query_all(
        """
        SELECT DATE(created_at) AS day, SUM(total_amount) AS revenue
        FROM invoices
        WHERE status = 'paid' AND DATE(created_at) BETWEEN %s AND %s
        GROUP BY DATE(created_at)
        ORDER BY day
        """,
        (start_date, end_date),
    )
    return ok({"summary": summary, "daily_breakdown": daily})


@reports_bp.route("/appointments", methods=["GET"])
@role_required("hospital_admin", "super_admin")
def appointment_statistics():
    start_date, end_date = _date_range()
    by_status = query_all(
        """
        SELECT status, COUNT(*) AS total
        FROM appointments
        WHERE appointment_date BETWEEN %s AND %s
        GROUP BY status
        """,
        (start_date, end_date),
    )
    return ok({"by_status": by_status})


@reports_bp.route("/patients", methods=["GET"])
@role_required("hospital_admin", "super_admin")
def patient_statistics():
    start_date, end_date = _date_range()
    total_patients = query_one("SELECT COUNT(*) AS total FROM patients")["total"]
    new_patients = query_one(
        "SELECT COUNT(*) AS total FROM patients WHERE DATE(created_at) BETWEEN %s AND %s",
        (start_date, end_date),
    )["total"]
    by_gender = query_all("SELECT gender, COUNT(*) AS total FROM patients GROUP BY gender")
    return ok({
        "total_patients": total_patients,
        "new_patients_in_range": new_patients,
        "by_gender": by_gender,
    })


@reports_bp.route("/pharmacy-sales", methods=["GET"])
@role_required("hospital_admin", "super_admin", "pharmacist")
def pharmacy_sales_report():
    start_date, end_date = _date_range()
    summary = query_one(
        """
        SELECT COALESCE(SUM(total_price), 0) AS total_sales, COUNT(*) AS sale_count
        FROM pharmacy_sales
        WHERE DATE(sold_at) BETWEEN %s AND %s
        """,
        (start_date, end_date),
    )
    top_medicines = query_all(
        """
        SELECT m.name, SUM(s.quantity) AS total_quantity_sold, SUM(s.total_price) AS total_revenue
        FROM pharmacy_sales s
        JOIN medicines m ON m.id = s.medicine_id
        WHERE DATE(s.sold_at) BETWEEN %s AND %s
        GROUP BY m.id
        ORDER BY total_quantity_sold DESC
        LIMIT 10
        """,
        (start_date, end_date),
    )
    return ok({"summary": summary, "top_medicines": top_medicines})


@reports_bp.route("/doctor-performance", methods=["GET"])
@role_required("hospital_admin", "super_admin")
def doctor_performance_report():
    start_date, end_date = _date_range()
    rows = query_all(
        """
        SELECT d.id AS doctor_id, u.first_name, u.last_name,
               COUNT(a.id) AS total_appointments,
               SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) AS completed_appointments
        FROM doctors d
        JOIN users u ON u.id = d.user_id
        LEFT JOIN appointments a ON a.doctor_id = d.id AND a.appointment_date BETWEEN %s AND %s
        GROUP BY d.id
        ORDER BY total_appointments DESC
        """,
        (start_date, end_date),
    )
    return ok(rows)
