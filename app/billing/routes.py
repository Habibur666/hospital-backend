"""
Billing Module — invoice generation with tax/discount, payment methods, PDF invoice.
"""
import os
from flask import Blueprint, request, current_app, send_file
from fpdf import FPDF
from app.db import query_all, query_one, execute
from app.helpers import ok, fail, get_pagination_params, paginated, verify_patient_self_access
from app.decorators import role_required, login_required
from app.audit_log import log_action
from flask_jwt_extended import get_jwt_identity, get_jwt

billing_bp = Blueprint("billing", __name__)


@billing_bp.route("/invoices", methods=["GET"])
@role_required("cashier", "hospital_admin", "super_admin")
def list_invoices():
    page, per_page, offset = get_pagination_params()
    status = request.args.get("status")

    sql = "SELECT * FROM invoices WHERE 1=1"
    count_sql = "SELECT COUNT(*) AS total FROM invoices WHERE 1=1"
    params = []
    if status:
        sql += " AND status = %s"
        count_sql += " AND status = %s"
        params.append(status)

    total = query_one(count_sql, tuple(params))["total"]
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    rows = query_all(sql, tuple(params) + (per_page, offset))
    return paginated(rows, page, per_page, total)


@billing_bp.route("/invoices", methods=["POST"])
@role_required("cashier", "hospital_admin", "super_admin")
def create_invoice():
    """
    Expected body:
    {
      "patient_id": 1,
      "items": [{"description": "Consultation", "quantity": 1, "unit_price": 500}],
      "tax_amount": 25,
      "discount_amount": 0,
      "payment_method": "cash"
    }
    Note: tax_amount and discount_amount are flat dollar amounts (not
    percentages), matching the `invoices` table columns.
    """
    data = request.get_json() or {}
    if not data.get("patient_id") or not data.get("items"):
        return fail("'patient_id' and 'items' are required", 422)

    items = data["items"]
    subtotal = sum(float(i["unit_price"]) * int(i.get("quantity", 1)) for i in items)
    tax_amount = float(data.get("tax_amount", 0))
    discount_amount = float(data.get("discount_amount", 0))
    total_amount = round(subtotal + tax_amount - discount_amount, 2)

    invoice_id = execute(
        """
        INSERT INTO invoices (patient_id, subtotal, tax_amount, discount_amount, total_amount, payment_method, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (data["patient_id"], subtotal, tax_amount, discount_amount, total_amount,
         data.get("payment_method"), get_jwt_identity()),
    )

    for item in items:
        execute(
            "INSERT INTO invoice_items (invoice_id, description, quantity, unit_price) VALUES (%s, %s, %s, %s)",
            (invoice_id, item["description"], item.get("quantity", 1), item["unit_price"]),
        )

    log_action(get_jwt_identity(), "create_invoice", "invoice", invoice_id)

    invoice = query_one("SELECT * FROM invoices WHERE id = %s", (invoice_id,))
    invoice["items"] = query_all("SELECT * FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
    return ok(invoice, "Invoice created", 201)


@billing_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
@role_required("cashier", "hospital_admin", "super_admin", "patient")
def get_invoice(invoice_id):
    invoice = query_one("SELECT * FROM invoices WHERE id = %s", (invoice_id,))
    if not invoice:
        return fail("Invoice not found", 404)
    denied = verify_patient_self_access(invoice["patient_id"])
    if denied:
        return denied
    invoice["items"] = query_all("SELECT * FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
    return ok(invoice)


@billing_bp.route("/invoices/<int:invoice_id>/pay", methods=["PATCH"])
@role_required("cashier", "hospital_admin", "super_admin")
def pay_invoice(invoice_id):
    data = request.get_json() or {}
    status = data.get("status", "paid")
    valid_statuses = ["unpaid", "paid", "partially_paid", "cancelled"]
    if status not in valid_statuses:
        return fail(f"'status' must be one of {valid_statuses}", 422)

    invoice = query_one("SELECT id FROM invoices WHERE id = %s", (invoice_id,))
    if not invoice:
        return fail("Invoice not found", 404)

    execute("UPDATE invoices SET status = %s, payment_method = %s WHERE id = %s",
            (status, data.get("payment_method"), invoice_id))
    log_action(get_jwt_identity(), "pay_invoice", "invoice", invoice_id, status)
    return ok(query_one("SELECT * FROM invoices WHERE id = %s", (invoice_id,)), "Invoice payment updated")


@billing_bp.route("/invoices/<int:invoice_id>/pdf", methods=["GET"])
@role_required("cashier", "hospital_admin", "super_admin", "patient")
def generate_invoice_pdf(invoice_id):
    invoice = query_one(
        """
        SELECT i.*, p.first_name, p.last_name
        FROM invoices i JOIN patients p ON p.id = i.patient_id
        WHERE i.id = %s
        """,
        (invoice_id,),
    )
    if not invoice:
        return fail("Invoice not found", 404)
    denied = verify_patient_self_access(invoice["patient_id"])
    if denied:
        return denied

    items = query_all("SELECT * FROM invoice_items WHERE invoice_id = %s", (invoice_id,))

    # Build a very simple PDF invoice
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Hospital Invoice", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Invoice #: {invoice['id']}", ln=True)
    pdf.cell(0, 8, f"Patient: {invoice['first_name']} {invoice['last_name']}", ln=True)
    pdf.cell(0, 8, f"Date: {invoice['created_at']}", ln=True)
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(90, 8, "Description", border=1)
    pdf.cell(30, 8, "Qty", border=1)
    pdf.cell(35, 8, "Unit Price", border=1)
    pdf.cell(35, 8, "Line Total", border=1, ln=True)

    pdf.set_font("Helvetica", "", 11)
    for item in items:
        line_total = float(item["unit_price"]) * item["quantity"]
        pdf.cell(90, 8, str(item["description"]), border=1)
        pdf.cell(30, 8, str(item["quantity"]), border=1)
        pdf.cell(35, 8, f"{item['unit_price']:.2f}", border=1)
        pdf.cell(35, 8, f"{line_total:.2f}", border=1, ln=True)

    pdf.ln(5)
    pdf.cell(0, 8, f"Subtotal: {invoice['subtotal']}", ln=True)
    pdf.cell(0, 8, f"Tax: {invoice['tax_amount']}", ln=True)
    pdf.cell(0, 8, f"Discount: {invoice['discount_amount']}", ln=True)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Total: {invoice['total_amount']}", ln=True)

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    output_path = os.path.join(upload_folder, f"invoice_{invoice_id}.pdf")
    pdf.output(output_path)

    return send_file(output_path, as_attachment=True, download_name=f"invoice_{invoice_id}.pdf")
