"""
Audit Logs Module — read-only view of who did what, for admins.
"""
from flask import Blueprint, request
from app.db import query_all, query_one
from app.helpers import get_pagination_params, paginated
from app.decorators import role_required

audit_bp = Blueprint("audit", __name__)


@audit_bp.route("", methods=["GET"])
@role_required("super_admin", "hospital_admin")
def list_audit_logs():
    page, per_page, offset = get_pagination_params()
    user_id = request.args.get("user_id")

    sql = "SELECT * FROM audit_logs WHERE 1=1"
    count_sql = "SELECT COUNT(*) AS total FROM audit_logs WHERE 1=1"
    params = []
    if user_id:
        sql += " AND user_id = %s"
        count_sql += " AND user_id = %s"
        params.append(user_id)

    total = query_one(count_sql, tuple(params))["total"]
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    rows = query_all(sql, tuple(params) + (per_page, offset))
    return paginated(rows, page, per_page, total)
