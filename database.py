"""Small MySQL helper functions used by the Flask routes."""

from pathlib import Path
import re

import click
import mysql.connector
from flask import current_app, g
from werkzeug.security import generate_password_hash


def mysql_settings(include_database=True):
    """Return connector settings from Flask configuration."""
    settings = {
        "host": current_app.config["MYSQL_HOST"],
        "port": current_app.config["MYSQL_PORT"],
        "user": current_app.config["MYSQL_USER"],
        "password": current_app.config["MYSQL_PASSWORD"],
    }
    if include_database:
        settings["database"] = current_app.config["MYSQL_DATABASE"]
    return settings


def get_db():
    """Open one database connection per request and keep it on Flask's g."""
    if "db" not in g:
        g.db = mysql.connector.connect(**mysql_settings())
    return g.db


def get_cursor(dictionary=True):
    return get_db().cursor(dictionary=dictionary)


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None and connection.is_connected():
        connection.close()


def execute_script(cursor, filename):
    """Execute a .sql file containing the application's schema."""
    path = Path(current_app.root_path) / filename
    script = path.read_text(encoding="utf-8")
    # schema.sql deliberately contains ordinary CREATE TABLE statements only,
    # so splitting on semicolons keeps this compatible across connector versions.
    for statement in script.split(";"):
        if statement.strip():
            cursor.execute(statement)


def seed_database(connection):
    """Insert a safe, realistic starter account and data only once."""
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id FROM users LIMIT 1")
    if cursor.fetchone():
        return False

    cursor.execute(
        """INSERT INTO users (full_name, username, password_hash, role)
           VALUES (%s, %s, %s, %s)""",
        ("Aarav Mehta", "admin", generate_password_hash("admin123"), "Admin"),
    )

    categories = [
        ("Beverages", "Cold drinks, juices and packaged water"),
        ("Office Supplies", "Stationery and daily office consumables"),
        ("Electronics", "Small electronic accessories"),
        ("Home Care", "Cleaning and household products"),
    ]
    cursor.executemany(
        "INSERT INTO categories (name, description) VALUES (%s, %s)", categories
    )
    suppliers = [
        ("Metro Wholesale Traders", "Rohit Sharma", "9876543210", "sales@metrowholesale.in", "Andheri East, Mumbai"),
        ("Pune Stationers", "Priya Kulkarni", "9822012345", "hello@punestationers.in", "Shivaji Nagar, Pune"),
        ("TechKart Distributors", "Kunal Shah", "9898989898", "orders@techkart.in", "Viman Nagar, Pune"),
    ]
    cursor.executemany(
        """INSERT INTO suppliers (name, contact_person, phone, email, address)
           VALUES (%s, %s, %s, %s, %s)""",
        suppliers,
    )
    products = [
        ("Mineral Water 1 Litre", "BEV-001", 1, 1, 12.00, 20.00, 48, 15, "Bisleri-style packaged drinking water"),
        ("Cold Coffee 200 ml", "BEV-002", 1, 1, 42.00, 65.00, 7, 12, "Ready-to-drink cold coffee"),
        ("A4 Copier Paper (500 sheets)", "OFF-001", 2, 2, 245.00, 310.00, 18, 10, "75 GSM white copier paper"),
        ("Blue Ball Pen Pack of 10", "OFF-002", 2, 2, 55.00, 95.00, 24, 8, "Smooth-writing blue ink pens"),
        ("Wireless Mouse", "ELE-001", 3, 3, 380.00, 599.00, 5, 10, "2.4 GHz USB wireless mouse"),
        ("Surface Cleaner 500 ml", "HOM-001", 4, 1, 78.00, 125.00, 31, 10, "Multipurpose lemon fragrance cleaner"),
    ]
    cursor.executemany(
        """INSERT INTO products
           (name, sku, category_id, supplier_id, purchase_price, sale_price,
            current_stock, reorder_level, description)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        products,
    )
    cursor.execute("SELECT id, current_stock FROM products")
    movements = [
        (row["id"], "OPENING", row["current_stock"], "Opening balance", 1)
        for row in cursor.fetchall()
    ]
    cursor.executemany(
        """INSERT INTO stock_movements
           (product_id, movement_type, quantity, note, created_by)
           VALUES (%s, %s, %s, %s, %s)""",
        movements,
    )
    connection.commit()
    return True


def init_database():
    """Create the configured database, tables, and first sample data."""
    db_name = current_app.config["MYSQL_DATABASE"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise click.ClickException("MYSQL_DATABASE may contain only letters, numbers, and underscores.")

    server_connection = mysql.connector.connect(**mysql_settings(include_database=False))
    cursor = server_connection.cursor()
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    server_connection.close()

    connection = mysql.connector.connect(**mysql_settings())
    cursor = connection.cursor()
    execute_script(cursor, "schema.sql")
    connection.commit()
    was_seeded = seed_database(connection)
    connection.close()
    return was_seeded
