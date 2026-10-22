"""Dashboard, catalogue, stock, purchase, and sales routes."""

from collections import defaultdict
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from mysql.connector import Error

from database import get_cursor, get_db
from utils import decimal_or_none, login_required, positive_number


inventory_bp = Blueprint("inventory", __name__)


def find_product(product_id, active_only=False):
    cursor = get_cursor()
    sql = """SELECT p.*, c.name AS category_name, s.name AS supplier_name
             FROM products p
             LEFT JOIN categories c ON c.id = p.category_id
             LEFT JOIN suppliers s ON s.id = p.supplier_id
             WHERE p.id = %s"""
    if active_only:
        sql += " AND p.is_active = 1"
    cursor.execute(sql, (product_id,))
    product = cursor.fetchone()
    if not product:
        abort(404)
    return product


def catalogue_options():
    cursor = get_cursor()
    cursor.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cursor.fetchall()
    cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
    suppliers = cursor.fetchall()
    return categories, suppliers


def product_form_values():
    """Validate product form input and return database-ready values."""
    name = request.form.get("name", "").strip()
    sku = request.form.get("sku", "").strip().upper()
    purchase_price = decimal_or_none(request.form.get("purchase_price"))
    sale_price = decimal_or_none(request.form.get("sale_price"))
    reorder_level = decimal_or_none(request.form.get("reorder_level", "0"))
    opening_stock = decimal_or_none(request.form.get("current_stock", "0"))
    category_id = request.form.get("category_id") or None
    supplier_id = request.form.get("supplier_id") or None
    description = request.form.get("description", "").strip() or None

    if not name or not sku:
        return None, "Product name and SKU are required."
    if purchase_price is None or purchase_price < 0 or sale_price is None or sale_price < 0:
        return None, "Purchase and sale prices must be valid positive amounts."
    if reorder_level is None or reorder_level < 0 or opening_stock is None or opening_stock < 0:
        return None, "Stock and reorder level cannot be negative."
    return {
        "name": name,
        "sku": sku,
        "category_id": category_id,
        "supplier_id": supplier_id,
        "purchase_price": purchase_price,
        "sale_price": sale_price,
        "current_stock": opening_stock,
        "reorder_level": reorder_level,
        "description": description,
    }, None


def parse_line_items(price_field):
    """Read the dynamic line-item fields sent by purchase/sale forms."""
    product_ids = request.form.getlist("product_id[]")
    quantities = request.form.getlist("quantity[]")
    prices = request.form.getlist(price_field)
    if not product_ids or not (len(product_ids) == len(quantities) == len(prices)):
        return None, "Add at least one complete product line."

    items = []
    used_product_ids = set()
    for product_id, quantity_value, price_value in zip(product_ids, quantities, prices):
        quantity = positive_number(quantity_value)
        price = positive_number(price_value)
        if not product_id or quantity is None or price is None:
            return None, "Each line needs a product, quantity, and price greater than zero."
        try:
            parsed_product_id = int(product_id)
        except ValueError:
            return None, "One of the selected products is invalid."
        if parsed_product_id in used_product_ids:
            return None, "Please add each product only once in a transaction."
        used_product_ids.add(parsed_product_id)
        items.append({"product_id": parsed_product_id, "quantity": quantity, "price": price})
    return items, None


def next_invoice_number(prefix, table_name, column_name):
    today = date.today().strftime("%Y%m%d")
    cursor = get_cursor()
    cursor.execute(
        f"SELECT COUNT(*) AS total FROM {table_name} WHERE {column_name} LIKE %s",
        (f"{prefix}-{today}-%",),
    )
    return f"{prefix}-{today}-{cursor.fetchone()['total'] + 1:03d}"


@inventory_bp.get("/dashboard")
@login_required
def dashboard():
    cursor = get_cursor()
    cursor.execute(
        """SELECT COUNT(*) AS total_products, COALESCE(SUM(current_stock), 0) AS total_stock,
                  COALESCE(SUM(current_stock * purchase_price), 0) AS stock_value
           FROM products WHERE is_active = 1"""
    )
    summary = cursor.fetchone()
    cursor.execute(
        """SELECT COUNT(*) AS total FROM products
           WHERE is_active = 1 AND current_stock <= reorder_level"""
    )
    summary["low_stock"] = cursor.fetchone()["total"]
    cursor.execute(
        """SELECT COALESCE(SUM(total_amount), 0) AS total FROM sales
           WHERE DATE(sale_date) = CURDATE()"""
    )
    summary["today_sales"] = cursor.fetchone()["total"]
    cursor.execute(
        """SELECT p.id, p.name, p.sku, p.current_stock, p.reorder_level, c.name AS category_name
           FROM products p LEFT JOIN categories c ON c.id = p.category_id
           WHERE p.is_active = 1 AND p.current_stock <= p.reorder_level
           ORDER BY p.current_stock ASC LIMIT 6"""
    )
    low_stock_products = cursor.fetchall()
    cursor.execute(
        """SELECT sm.*, p.name AS product_name, p.sku, u.full_name AS user_name
           FROM stock_movements sm
           JOIN products p ON p.id = sm.product_id
           LEFT JOIN users u ON u.id = sm.created_by
           ORDER BY sm.created_at DESC LIMIT 8"""
    )
    recent_movements = cursor.fetchall()
    return render_template(
        "dashboard.html", summary=summary, low_stock_products=low_stock_products, recent_movements=recent_movements
    )


@inventory_bp.get("/products")
@login_required
def products():
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", "").strip()
    low_stock_only = request.args.get("low_stock") == "1"
    cursor = get_cursor()
    sql = """SELECT p.*, c.name AS category_name, s.name AS supplier_name
             FROM products p
             LEFT JOIN categories c ON c.id = p.category_id
             LEFT JOIN suppliers s ON s.id = p.supplier_id
             WHERE p.is_active = 1"""
    params = []
    if search:
        sql += " AND (p.name LIKE %s OR p.sku LIKE %s OR COALESCE(c.name, '') LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term])
    if category_id.isdigit():
        sql += " AND p.category_id = %s"
        params.append(category_id)
    if low_stock_only:
        sql += " AND p.current_stock <= p.reorder_level"
    sql += " ORDER BY p.created_at DESC"
    cursor.execute(sql, tuple(params))
    product_list = cursor.fetchall()
    categories, _suppliers = catalogue_options()
    return render_template(
        "products/list.html",
        products=product_list,
        categories=categories,
        search=search,
        selected_category=category_id,
        low_stock_only=low_stock_only,
    )


@inventory_bp.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product():
    categories, suppliers = catalogue_options()
    if request.method == "POST":
        values, error = product_form_values()
        if error:
            flash(error, "danger")
        else:
            cursor = get_cursor()
            try:
                cursor.execute(
                    """INSERT INTO products
                       (name, sku, category_id, supplier_id, purchase_price, sale_price,
                        current_stock, reorder_level, description)
                       VALUES (%(name)s, %(sku)s, %(category_id)s, %(supplier_id)s,
                               %(purchase_price)s, %(sale_price)s, %(current_stock)s,
                               %(reorder_level)s, %(description)s)""",
                    values,
                )
                product_id = cursor.lastrowid
                if values["current_stock"] > 0:
                    cursor.execute(
                        """INSERT INTO stock_movements
                           (product_id, movement_type, quantity, note, created_by)
                           VALUES (%s, 'OPENING', %s, 'Opening stock while creating product', %s)""",
                        (product_id, values["current_stock"], session["user_id"]),
                    )
                get_db().commit()
                flash("Product added successfully.", "success")
                return redirect(url_for("inventory.products"))
            except Error as error:
                get_db().rollback()
                flash(f"Could not add product: {error.msg}", "danger")
    return render_template("products/form.html", product=None, categories=categories, suppliers=suppliers)


@inventory_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = find_product(product_id)
    categories, suppliers = catalogue_options()
    if request.method == "POST":
        values, error = product_form_values()
        if error:
            flash(error, "danger")
        else:
            # Stock is intentionally not changed here. It must be auditable via Stock In/Out.
            values["current_stock"] = product["current_stock"]
            cursor = get_cursor()
            try:
                cursor.execute(
                    """UPDATE products SET name=%(name)s, sku=%(sku)s, category_id=%(category_id)s,
                       supplier_id=%(supplier_id)s, purchase_price=%(purchase_price)s,
                       sale_price=%(sale_price)s, reorder_level=%(reorder_level)s,
                       description=%(description)s WHERE id=%(id)s""",
                    {**values, "id": product_id},
                )
                get_db().commit()
                flash("Product details updated.", "success")
                return redirect(url_for("inventory.products"))
            except Error as error:
                get_db().rollback()
                flash(f"Could not update product: {error.msg}", "danger")
    return render_template("products/form.html", product=product, categories=categories, suppliers=suppliers)


@inventory_bp.post("/products/<int:product_id>/delete")
@login_required
def delete_product(product_id):
    product = find_product(product_id)
    cursor = get_cursor()
    cursor.execute("UPDATE products SET is_active = 0 WHERE id = %s", (product_id,))
    get_db().commit()
    flash(f"{product['name']} was archived. Its transaction history is retained.", "success")
    return redirect(url_for("inventory.products"))


@inventory_bp.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    cursor = get_cursor()
    edit_item = None
    edit_id = request.args.get("edit", "")
    if edit_id.isdigit():
        cursor.execute("SELECT * FROM categories WHERE id = %s", (edit_id,))
        edit_item = cursor.fetchone()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        category_id = request.form.get("category_id")
        if not name:
            flash("Category name is required.", "danger")
        else:
            try:
                if category_id:
                    cursor.execute("UPDATE categories SET name=%s, description=%s WHERE id=%s", (name, description, category_id))
                    flash("Category updated.", "success")
                else:
                    cursor.execute("INSERT INTO categories (name, description) VALUES (%s, %s)", (name, description))
                    flash("Category added.", "success")
                get_db().commit()
                return redirect(url_for("inventory.categories"))
            except Error as error:
                get_db().rollback()
                flash(f"Could not save category: {error.msg}", "danger")
    cursor.execute(
        """SELECT c.*, COUNT(p.id) AS product_count FROM categories c
           LEFT JOIN products p ON p.category_id = c.id AND p.is_active = 1
           GROUP BY c.id ORDER BY c.name"""
    )
    return render_template("categories/index.html", categories=cursor.fetchall(), edit_item=edit_item)


@inventory_bp.post("/categories/<int:category_id>/delete")
@login_required
def delete_category(category_id):
    cursor = get_cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM products WHERE category_id = %s", (category_id,))
    if cursor.fetchone()["total"]:
        flash("This category is used by products and cannot be deleted.", "warning")
    else:
        cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
        get_db().commit()
        flash("Category deleted.", "success")
    return redirect(url_for("inventory.categories"))


@inventory_bp.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers():
    cursor = get_cursor()
    edit_item = None
    edit_id = request.args.get("edit", "")
    if edit_id.isdigit():
        cursor.execute("SELECT * FROM suppliers WHERE id = %s", (edit_id,))
        edit_item = cursor.fetchone()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact_person = request.form.get("contact_person", "").strip() or None
        phone = request.form.get("phone", "").strip() or None
        email = request.form.get("email", "").strip() or None
        address = request.form.get("address", "").strip() or None
        supplier_id = request.form.get("supplier_id")
        if not name:
            flash("Supplier name is required.", "danger")
        else:
            try:
                values = (name, contact_person, phone, email, address)
                if supplier_id:
                    cursor.execute(
                        """UPDATE suppliers SET name=%s, contact_person=%s, phone=%s, email=%s, address=%s
                           WHERE id=%s""", values + (supplier_id,)
                    )
                    flash("Supplier updated.", "success")
                else:
                    cursor.execute(
                        """INSERT INTO suppliers (name, contact_person, phone, email, address)
                           VALUES (%s, %s, %s, %s, %s)""", values
                    )
                    flash("Supplier added.", "success")
                get_db().commit()
                return redirect(url_for("inventory.suppliers"))
            except Error as error:
                get_db().rollback()
                flash(f"Could not save supplier: {error.msg}", "danger")
    cursor.execute(
        """SELECT s.*, COUNT(p.id) AS product_count FROM suppliers s
           LEFT JOIN products p ON p.supplier_id = s.id AND p.is_active = 1
           GROUP BY s.id ORDER BY s.name"""
    )
    return render_template("suppliers/index.html", suppliers=cursor.fetchall(), edit_item=edit_item)


@inventory_bp.post("/suppliers/<int:supplier_id>/delete")
@login_required
def delete_supplier(supplier_id):
    cursor = get_cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM products WHERE supplier_id = %s", (supplier_id,))
    if cursor.fetchone()["total"]:
        flash("This supplier is linked to products and cannot be deleted.", "warning")
    else:
        cursor.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
        get_db().commit()
        flash("Supplier deleted.", "success")
    return redirect(url_for("inventory.suppliers"))


@inventory_bp.route("/stock", methods=["GET", "POST"])
@login_required
def stock():
    cursor = get_cursor()
    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        movement_type = request.form.get("movement_type")
        quantity = positive_number(request.form.get("quantity"))
        note = request.form.get("note", "").strip() or None
        if movement_type not in {"IN", "OUT"} or not product_id or quantity is None:
            flash("Choose a product, movement type, and valid quantity.", "danger")
        else:
            try:
                cursor.execute("SELECT * FROM products WHERE id=%s AND is_active=1 FOR UPDATE", (product_id,))
                product = cursor.fetchone()
                if not product:
                    flash("The selected product is no longer available.", "danger")
                elif movement_type == "OUT" and product["current_stock"] < quantity:
                    flash(f"Only {product['current_stock']} units of {product['name']} are available.", "danger")
                else:
                    sign = 1 if movement_type == "IN" else -1
                    cursor.execute(
                        "UPDATE products SET current_stock = current_stock + %s WHERE id = %s",
                        (sign * quantity, product_id),
                    )
                    cursor.execute(
                        """INSERT INTO stock_movements (product_id, movement_type, quantity, note, created_by)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (product_id, movement_type, quantity, note, session["user_id"]),
                    )
                    get_db().commit()
                    flash("Stock movement recorded.", "success")
                    return redirect(url_for("inventory.stock"))
            except Error as error:
                get_db().rollback()
                flash(f"Could not update stock: {error.msg}", "danger")
    cursor.execute("SELECT id, name, sku, current_stock FROM products WHERE is_active=1 ORDER BY name")
    product_list = cursor.fetchall()
    cursor.execute(
        """SELECT sm.*, p.name AS product_name, p.sku, u.full_name AS user_name
           FROM stock_movements sm JOIN products p ON p.id=sm.product_id
           LEFT JOIN users u ON u.id=sm.created_by ORDER BY sm.created_at DESC LIMIT 100"""
    )
    return render_template("stock/index.html", products=product_list, movements=cursor.fetchall())


@inventory_bp.get("/purchases")
@login_required
def purchases():
    cursor = get_cursor()
    cursor.execute(
        """SELECT pu.*, s.name AS supplier_name, u.full_name AS created_by_name,
                  COUNT(pi.id) AS item_count
           FROM purchases pu JOIN suppliers s ON s.id=pu.supplier_id
           LEFT JOIN users u ON u.id=pu.created_by LEFT JOIN purchase_items pi ON pi.purchase_id=pu.id
           GROUP BY pu.id ORDER BY pu.purchase_date DESC, pu.id DESC"""
    )
    return render_template("purchases/list.html", purchases=cursor.fetchall())


@inventory_bp.route("/purchases/new", methods=["GET", "POST"])
@login_required
def new_purchase():
    cursor = get_cursor()
    cursor.execute("SELECT id, name FROM suppliers ORDER BY name")
    supplier_list = cursor.fetchall()
    cursor.execute("SELECT id, name, sku, purchase_price, current_stock FROM products WHERE is_active=1 ORDER BY name")
    product_list = cursor.fetchall()
    if request.method == "POST":
        supplier_id = request.form.get("supplier_id", type=int)
        purchase_date = request.form.get("purchase_date") or str(date.today())
        invoice_number = request.form.get("invoice_number", "").strip() or next_invoice_number("PUR", "purchases", "invoice_number")
        notes = request.form.get("notes", "").strip() or None
        items, error = parse_line_items("unit_cost[]")
        if not supplier_id or error:
            flash(error or "Please select a supplier.", "danger")
        else:
            try:
                cursor.execute("SELECT id FROM suppliers WHERE id=%s", (supplier_id,))
                if not cursor.fetchone():
                    flash("Selected supplier does not exist.", "danger")
                    return render_template("purchases/form.html", suppliers=supplier_list, products=product_list, today=str(date.today()))
                total = sum(item["quantity"] * item["price"] for item in items)
                cursor.execute(
                    """INSERT INTO purchases (supplier_id, invoice_number, purchase_date, total_amount, notes, created_by)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (supplier_id, invoice_number, purchase_date, total, notes, session["user_id"]),
                )
                purchase_id = cursor.lastrowid
                for item in items:
                    cursor.execute("SELECT id FROM products WHERE id=%s AND is_active=1 FOR UPDATE", (item["product_id"],))
                    if not cursor.fetchone():
                        raise ValueError("A selected product is no longer available.")
                    cursor.execute(
                        """INSERT INTO purchase_items (purchase_id, product_id, quantity, unit_cost, subtotal)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (purchase_id, item["product_id"], item["quantity"], item["price"], item["quantity"] * item["price"]),
                    )
                    cursor.execute("UPDATE products SET current_stock=current_stock+%s WHERE id=%s", (item["quantity"], item["product_id"]))
                    cursor.execute(
                        """INSERT INTO stock_movements
                           (product_id, movement_type, quantity, reference_type, reference_id, note, created_by)
                           VALUES (%s, 'PURCHASE', %s, 'PURCHASE', %s, %s, %s)""",
                        (item["product_id"], item["quantity"], purchase_id, f"Purchase {invoice_number}", session["user_id"]),
                    )
                get_db().commit()
                flash("Purchase saved and stock updated.", "success")
                return redirect(url_for("inventory.purchase_invoice", purchase_id=purchase_id))
            except (Error, ValueError) as error:
                get_db().rollback()
                flash(f"Could not save purchase: {getattr(error, 'msg', str(error))}", "danger")
    return render_template("purchases/form.html", suppliers=supplier_list, products=product_list, today=str(date.today()))


@inventory_bp.get("/purchases/<int:purchase_id>/invoice")
@login_required
def purchase_invoice(purchase_id):
    cursor = get_cursor()
    cursor.execute(
        """SELECT pu.*, s.name AS supplier_name, s.contact_person, s.phone, s.email, s.address,
                  u.full_name AS created_by_name
           FROM purchases pu JOIN suppliers s ON s.id=pu.supplier_id
           LEFT JOIN users u ON u.id=pu.created_by WHERE pu.id=%s""", (purchase_id,)
    )
    purchase = cursor.fetchone()
    if not purchase:
        abort(404)
    cursor.execute(
        """SELECT pi.*, p.name AS product_name, p.sku FROM purchase_items pi
           JOIN products p ON p.id=pi.product_id WHERE pi.purchase_id=%s""", (purchase_id,)
    )
    return render_template("purchases/invoice.html", purchase=purchase, items=cursor.fetchall())


@inventory_bp.get("/sales")
@login_required
def sales():
    cursor = get_cursor()
    cursor.execute(
        """SELECT sa.*, u.full_name AS created_by_name, COUNT(si.id) AS item_count
           FROM sales sa LEFT JOIN users u ON u.id=sa.created_by LEFT JOIN sale_items si ON si.sale_id=sa.id
           GROUP BY sa.id ORDER BY sa.sale_date DESC, sa.id DESC"""
    )
    return render_template("sales/list.html", sales=cursor.fetchall())


@inventory_bp.route("/sales/new", methods=["GET", "POST"])
@login_required
def new_sale():
    cursor = get_cursor()
    cursor.execute("SELECT id, name, sku, sale_price, current_stock FROM products WHERE is_active=1 ORDER BY name")
    product_list = cursor.fetchall()
    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip() or "Walk-in Customer"
        customer_phone = request.form.get("customer_phone", "").strip() or None
        sale_date = request.form.get("sale_date") or str(date.today())
        invoice_number = request.form.get("invoice_number", "").strip() or next_invoice_number("INV", "sales", "invoice_number")
        notes = request.form.get("notes", "").strip() or None
        items, error = parse_line_items("unit_price[]")
        if error:
            flash(error, "danger")
        else:
            try:
                # Lock products before the sale so two users cannot sell the same last item.
                for item in items:
                    cursor.execute("SELECT name, current_stock FROM products WHERE id=%s AND is_active=1 FOR UPDATE", (item["product_id"],))
                    product = cursor.fetchone()
                    if not product:
                        raise ValueError("A selected product is no longer available.")
                    if product["current_stock"] < item["quantity"]:
                        raise ValueError(f"Only {product['current_stock']} units of {product['name']} are available.")
                total = sum(item["quantity"] * item["price"] for item in items)
                cursor.execute(
                    """INSERT INTO sales
                       (invoice_number, customer_name, customer_phone, sale_date, total_amount, notes, created_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (invoice_number, customer_name, customer_phone, sale_date, total, notes, session["user_id"]),
                )
                sale_id = cursor.lastrowid
                for item in items:
                    cursor.execute(
                        """INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (sale_id, item["product_id"], item["quantity"], item["price"], item["quantity"] * item["price"]),
                    )
                    cursor.execute("UPDATE products SET current_stock=current_stock-%s WHERE id=%s", (item["quantity"], item["product_id"]))
                    cursor.execute(
                        """INSERT INTO stock_movements
                           (product_id, movement_type, quantity, reference_type, reference_id, note, created_by)
                           VALUES (%s, 'SALE', %s, 'SALE', %s, %s, %s)""",
                        (item["product_id"], item["quantity"], sale_id, f"Sale {invoice_number}", session["user_id"]),
                    )
                get_db().commit()
                flash("Sale completed and invoice generated.", "success")
                return redirect(url_for("inventory.sale_invoice", sale_id=sale_id))
            except (Error, ValueError) as error:
                get_db().rollback()
                flash(f"Could not save sale: {getattr(error, 'msg', str(error))}", "danger")
    return render_template("sales/form.html", products=product_list, today=str(date.today()))


@inventory_bp.get("/sales/<int:sale_id>/invoice")
@login_required
def sale_invoice(sale_id):
    cursor = get_cursor()
    cursor.execute(
        """SELECT sa.*, u.full_name AS created_by_name FROM sales sa
           LEFT JOIN users u ON u.id=sa.created_by WHERE sa.id=%s""", (sale_id,)
    )
    sale = cursor.fetchone()
    if not sale:
        abort(404)
    cursor.execute(
        """SELECT si.*, p.name AS product_name, p.sku FROM sale_items si
           JOIN products p ON p.id=si.product_id WHERE si.sale_id=%s""", (sale_id,)
    )
    return render_template("sales/invoice.html", sale=sale, items=cursor.fetchall())
