"""
Pharmacy Module — medicine stock, expiry dates, low-stock alerts, sales.
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail, get_pagination_params, paginated
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity

pharmacy_bp = Blueprint("pharmacy", __name__)


@pharmacy_bp.route("/medicines", methods=["GET"])
@login_required
def list_medicines():
    page, per_page, offset = get_pagination_params()
    search = request.args.get("search")

    sql = "SELECT * FROM medicines WHERE 1=1"
    count_sql = "SELECT COUNT(*) AS total FROM medicines WHERE 1=1"
    params = []
    if search:
        sql += " AND name LIKE %s"
        count_sql += " AND name LIKE %s"
        params.append(f"%{search}%")

    total = query_one(count_sql, tuple(params))["total"]
    sql += " ORDER BY name LIMIT %s OFFSET %s"
    rows = query_all(sql, tuple(params) + (per_page, offset))
    return paginated(rows, page, per_page, total)


@pharmacy_bp.route("/medicines", methods=["POST"])
@role_required("pharmacist", "hospital_admin", "super_admin")
def create_medicine():
    data = request.get_json() or {}
    if not data.get("name"):
        return fail("'name' is required", 422)

    medicine_id = execute(
        """
        INSERT INTO medicines (name, category, unit_price, stock_qty, low_stock_threshold, expiry_date)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (data["name"], data.get("category"), data.get("unit_price", 0),
         data.get("stock_qty", 0), data.get("low_stock_threshold", 10), data.get("expiry_date")),
    )
    log_action(get_jwt_identity(), "create_medicine", "medicine", medicine_id)
    return ok(query_one("SELECT * FROM medicines WHERE id = %s", (medicine_id,)), "Medicine added", 201)


@pharmacy_bp.route("/medicines/<int:medicine_id>", methods=["PUT"])
@role_required("pharmacist", "hospital_admin", "super_admin")
def update_medicine(medicine_id):
    data = request.get_json() or {}
    medicine = query_one("SELECT id FROM medicines WHERE id = %s", (medicine_id,))
    if not medicine:
        return fail("Medicine not found", 404)

    fields, params = [], []
    for field in ["name", "category", "unit_price", "stock_qty", "low_stock_threshold", "expiry_date"]:
        if field in data:
            fields.append(f"{field} = %s")
            params.append(data[field])
    if not fields:
        return fail("No valid fields to update", 422)

    params.append(medicine_id)
    execute(f"UPDATE medicines SET {', '.join(fields)} WHERE id = %s", tuple(params))
    log_action(get_jwt_identity(), "update_medicine", "medicine", medicine_id)
    return ok(query_one("SELECT * FROM medicines WHERE id = %s", (medicine_id,)), "Medicine updated")


@pharmacy_bp.route("/medicines/low-stock", methods=["GET"])
@role_required("pharmacist", "hospital_admin", "super_admin")
def low_stock_alerts():
    rows = query_all("SELECT * FROM medicines WHERE stock_qty <= low_stock_threshold ORDER BY stock_qty")
    return ok(rows)


@pharmacy_bp.route("/medicines/expiring-soon", methods=["GET"])
@role_required("pharmacist", "hospital_admin", "super_admin")
def expiring_soon():
    days = request.args.get("days", 30)
    rows = query_all(
        "SELECT * FROM medicines WHERE expiry_date IS NOT NULL AND expiry_date <= DATE_ADD(CURDATE(), INTERVAL %s DAY) ORDER BY expiry_date",
        (days,),
    )
    return ok(rows)


@pharmacy_bp.route("/sales", methods=["POST"])
@role_required("pharmacist", "cashier", "hospital_admin", "super_admin")
def sell_medicine():
    data = request.get_json() or {}
    required_fields = ["medicine_id", "quantity"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    medicine = query_one("SELECT * FROM medicines WHERE id = %s", (data["medicine_id"],))
    if not medicine:
        return fail("Medicine not found", 404)

    quantity = int(data["quantity"])
    if medicine["stock_qty"] < quantity:
        return fail("Not enough stock available", 422)

    total_price = float(medicine["unit_price"]) * quantity

    sale_id = execute(
        "INSERT INTO pharmacy_sales (medicine_id, patient_id, quantity, total_price, sold_by) VALUES (%s, %s, %s, %s, %s)",
        (data["medicine_id"], data.get("patient_id"), quantity, total_price, get_jwt_identity()),
    )
    execute("UPDATE medicines SET stock_qty = stock_qty - %s WHERE id = %s", (quantity, data["medicine_id"]))

    log_action(get_jwt_identity(), "sell_medicine", "pharmacy_sale", sale_id)
    return ok(query_one("SELECT * FROM pharmacy_sales WHERE id = %s", (sale_id,)), "Sale recorded", 201)


@pharmacy_bp.route("/sales", methods=["GET"])
@role_required("pharmacist", "cashier", "hospital_admin", "super_admin")
def list_sales():
    page, per_page, offset = get_pagination_params()
    total = query_one("SELECT COUNT(*) AS total FROM pharmacy_sales")["total"]
    rows = query_all(
        """
        SELECT s.*, m.name AS medicine_name
        FROM pharmacy_sales s
        JOIN medicines m ON m.id = s.medicine_id
        ORDER BY s.sold_at DESC LIMIT %s OFFSET %s
        """,
        (per_page, offset),
    )
    return paginated(rows, page, per_page, total)
