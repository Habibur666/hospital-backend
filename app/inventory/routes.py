"""
Inventory Module — suppliers, stock in/out, purchase orders.
"""
from flask import Blueprint, request
from app.db import query_all, query_one, execute
from app.helpers import ok, fail, get_pagination_params, paginated
from app.decorators import role_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity

inventory_bp = Blueprint("inventory", __name__)


# ---------------- Suppliers ----------------

@inventory_bp.route("/suppliers", methods=["GET"])
@role_required("hospital_admin", "super_admin", "pharmacist")
def list_suppliers():
    return ok(query_all("SELECT * FROM suppliers ORDER BY name"))


@inventory_bp.route("/suppliers", methods=["POST"])
@role_required("hospital_admin", "super_admin")
def create_supplier():
    data = request.get_json() or {}
    if not data.get("name"):
        return fail("'name' is required", 422)

    supplier_id = execute(
        "INSERT INTO suppliers (name, phone, email, address) VALUES (%s, %s, %s, %s)",
        (data["name"], data.get("phone"), data.get("email"), data.get("address")),
    )
    log_action(get_jwt_identity(), "create_supplier", "supplier", supplier_id)
    return ok(query_one("SELECT * FROM suppliers WHERE id = %s", (supplier_id,)), "Supplier added", 201)


@inventory_bp.route("/suppliers/<int:supplier_id>", methods=["DELETE"])
@role_required("hospital_admin", "super_admin")
def delete_supplier(supplier_id):
    execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
    log_action(get_jwt_identity(), "delete_supplier", "supplier", supplier_id)
    return ok(None, "Supplier deleted")


# ---------------- Purchase Orders ----------------

@inventory_bp.route("/purchase-orders", methods=["GET"])
@role_required("hospital_admin", "super_admin", "pharmacist")
def list_purchase_orders():
    page, per_page, offset = get_pagination_params()
    total = query_one("SELECT COUNT(*) AS total FROM purchase_orders")["total"]
    rows = query_all(
        """
        SELECT po.*, s.name AS supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        ORDER BY po.ordered_at DESC LIMIT %s OFFSET %s
        """,
        (per_page, offset),
    )
    return paginated(rows, page, per_page, total)


@inventory_bp.route("/purchase-orders", methods=["POST"])
@role_required("hospital_admin", "super_admin", "pharmacist")
def create_purchase_order():
    data = request.get_json() or {}
    required_fields = ["supplier_id", "item_name", "quantity", "unit_price"]
    for field in required_fields:
        if not data.get(field):
            return fail(f"'{field}' is required", 422)

    order_id = execute(
        "INSERT INTO purchase_orders (supplier_id, item_name, quantity, unit_price) VALUES (%s, %s, %s, %s)",
        (data["supplier_id"], data["item_name"], data["quantity"], data["unit_price"]),
    )
    log_action(get_jwt_identity(), "create_purchase_order", "purchase_order", order_id)
    return ok(query_one("SELECT * FROM purchase_orders WHERE id = %s", (order_id,)), "Purchase order created", 201)


@inventory_bp.route("/purchase-orders/<int:order_id>/receive", methods=["PATCH"])
@role_required("hospital_admin", "super_admin", "pharmacist")
def receive_purchase_order(order_id):
    order = query_one("SELECT * FROM purchase_orders WHERE id = %s", (order_id,))
    if not order:
        return fail("Purchase order not found", 404)

    execute("UPDATE purchase_orders SET status = 'received', received_at = NOW() WHERE id = %s", (order_id,))
    execute(
        "INSERT INTO stock_movements (item_name, movement_type, quantity, reason) VALUES (%s, 'in', %s, %s)",
        (order["item_name"], order["quantity"], f"Purchase order #{order_id} received"),
    )
    log_action(get_jwt_identity(), "receive_purchase_order", "purchase_order", order_id)
    return ok(query_one("SELECT * FROM purchase_orders WHERE id = %s", (order_id,)), "Purchase order received")


# ---------------- Stock movements ----------------

@inventory_bp.route("/stock", methods=["GET"])
@role_required("hospital_admin", "super_admin", "pharmacist")
def list_stock_movements():
    return ok(query_all("SELECT * FROM stock_movements ORDER BY created_at DESC LIMIT 100"))


@inventory_bp.route("/stock/in", methods=["POST"])
@role_required("hospital_admin", "super_admin", "pharmacist")
def stock_in():
    data = request.get_json() or {}
    if not data.get("item_name") or not data.get("quantity"):
        return fail("'item_name' and 'quantity' are required", 422)

    movement_id = execute(
        "INSERT INTO stock_movements (item_name, movement_type, quantity, reason) VALUES (%s, 'in', %s, %s)",
        (data["item_name"], data["quantity"], data.get("reason")),
    )
    log_action(get_jwt_identity(), "stock_in", "stock_movement", movement_id)
    return ok(query_one("SELECT * FROM stock_movements WHERE id = %s", (movement_id,)), "Stock added", 201)


@inventory_bp.route("/stock/out", methods=["POST"])
@role_required("hospital_admin", "super_admin", "pharmacist")
def stock_out():
    data = request.get_json() or {}
    if not data.get("item_name") or not data.get("quantity"):
        return fail("'item_name' and 'quantity' are required", 422)

    movement_id = execute(
        "INSERT INTO stock_movements (item_name, movement_type, quantity, reason) VALUES (%s, 'out', %s, %s)",
        (data["item_name"], data["quantity"], data.get("reason")),
    )
    log_action(get_jwt_identity(), "stock_out", "stock_movement", movement_id)
    return ok(query_one("SELECT * FROM stock_movements WHERE id = %s", (movement_id,)), "Stock removed", 201)
