"""Application entry point for the Inventory Management System."""

import os

import click
from dotenv import load_dotenv
from flask import Flask, render_template, session

load_dotenv()

from auth import auth_bp
from config import Config
from database import close_db, get_cursor, init_database
from inventory import inventory_bp
from reports import reports_bp
from utils import indian_currency


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.teardown_appcontext(close_db)
    app.jinja_env.filters["inr"] = indian_currency

    @app.context_processor
    def inject_sidebar_data():
        """Show the signed-in name and live low-stock count in the sidebar."""
        if "user_id" not in session:
            return {}
        try:
            cursor = get_cursor()
            cursor.execute(
                """SELECT COUNT(*) AS total FROM products
                   WHERE is_active = 1 AND current_stock <= reorder_level"""
            )
            low_stock_count = cursor.fetchone()["total"]
        except Exception:
            low_stock_count = 0
        return {"sidebar_low_stock_count": low_stock_count, "current_user_name": session.get("user_name")}

    @app.cli.command("init-db")
    def initialise_database_command():
        """Create MySQL tables and add sample data: flask --app app init-db."""
        seeded = init_database()
        message = "Database tables created and sample data added." if seeded else "Database tables are ready; existing data was preserved."
        click.echo(message)

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(reports_bp)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
