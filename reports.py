"""Date-range reports and CSV export."""

import csv
from datetime import date
from io import StringIO

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from database import get_cursor
from utils import login_required


reports_bp = Blueprint("reports", __name__)


def selected_dates():
    """Use current month by default and keep an invalid range from reaching SQL."""
    today = date.today()
    start = request.args.get("start_date") or today.replace(day=1).isoformat()
    end = request.args.get("end_date") or today.isoformat()
    if start > end:
        start, end = end, start
    return start, end


def report_rows(start_date, end_date):
    cursor = get_cursor()
    cursor.execute(
        """SELECT COALESCE(SUM(total_amount), 0) AS total, COUNT(*) AS count
           FROM sales WHERE sale_date BETWEEN %s AND %s""", (start_date, end_date)
    )
    sales_summary = cursor.fetchone()
    cursor.execute(
        """SELECT COALESCE(SUM(total_amount), 0) AS total, COUNT(*) AS count
           FROM purchases WHERE purchase_date BETWEEN %s AND %s""", (start_date, end_date)
    )
    purchase_summary = cursor.fetchone()
    cursor.execute(
        """SELECT sa.invoice_number, sa.sale_date, sa.customer_name, sa.total_amount,
                  u.full_name AS created_by_name
           FROM sales sa LEFT JOIN users u ON u.id=sa.created_by
           WHERE sa.sale_date BETWEEN %s AND %s ORDER BY sa.sale_date DESC, sa.id DESC""", (start_date, end_date)
    )
    sales_rows = cursor.fetchall()
    cursor.execute(
        """SELECT pu.invoice_number, pu.purchase_date, su.name AS supplier_name, pu.total_amount,
                  u.full_name AS created_by_name
           FROM purchases pu JOIN suppliers su ON su.id=pu.supplier_id
           LEFT JOIN users u ON u.id=pu.created_by
           WHERE pu.purchase_date BETWEEN %s AND %s ORDER BY pu.purchase_date DESC, pu.id DESC""", (start_date, end_date)
    )
    purchase_rows = cursor.fetchall()
    cursor.execute(
        """SELECT p.name, p.sku, p.current_stock, p.reorder_level, c.name AS category_name
           FROM products p LEFT JOIN categories c ON c.id=p.category_id
           WHERE p.is_active=1 AND p.current_stock <= p.reorder_level
           ORDER BY p.current_stock ASC, p.name"""
    )
    low_stock_rows = cursor.fetchall()
    cursor.execute(
        """SELECT p.name, p.sku, SUM(si.quantity) AS quantity_sold, SUM(si.subtotal) AS sales_value
           FROM sale_items si JOIN sales sa ON sa.id=si.sale_id JOIN products p ON p.id=si.product_id
           WHERE sa.sale_date BETWEEN %s AND %s
           GROUP BY p.id ORDER BY quantity_sold DESC LIMIT 5""", (start_date, end_date)
    )
    top_products = cursor.fetchall()
    return sales_summary, purchase_summary, sales_rows, purchase_rows, low_stock_rows, top_products


@reports_bp.get("/reports")
@login_required
def reports():
    start_date, end_date = selected_dates()
    values = report_rows(start_date, end_date)
    return render_template(
        "reports/index.html",
        start_date=start_date,
        end_date=end_date,
        sales_summary=values[0],
        purchase_summary=values[1],
        sales_rows=values[2],
        purchase_rows=values[3],
        low_stock_rows=values[4],
        top_products=values[5],
    )


@reports_bp.get("/reports/export/<report_type>")
@login_required
def export_report(report_type):
    start_date, end_date = selected_dates()
    values = report_rows(start_date, end_date)
    output = StringIO()
    writer = csv.writer(output)
    if report_type == "sales":
        writer.writerow(["Invoice No.", "Date", "Customer", "Amount (INR)", "Created by"])
        writer.writerows([[row["invoice_number"], row["sale_date"], row["customer_name"], row["total_amount"], row["created_by_name"]] for row in values[2]])
    elif report_type == "purchases":
        writer.writerow(["Purchase No.", "Date", "Supplier", "Amount (INR)", "Created by"])
        writer.writerows([[row["invoice_number"], row["purchase_date"], row["supplier_name"], row["total_amount"], row["created_by_name"]] for row in values[3]])
    elif report_type == "low-stock":
        writer.writerow(["Product", "SKU", "Category", "Current stock", "Reorder level"])
        writer.writerows([[row["name"], row["sku"], row["category_name"], row["current_stock"], row["reorder_level"]] for row in values[4]])
    else:
        flash("Unknown report type.", "danger")
        return redirect(url_for("reports.reports"))
    filename = f"{report_type}-report-{start_date}-to-{end_date}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
