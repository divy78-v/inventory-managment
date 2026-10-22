"""Configuration for the Inventory Management System.

Values can be changed in a local .env file or operating-system environment
variables. Never commit real production credentials to Git.
"""

import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-before-production")
    # MYSQL_* is used locally. The second name supports Railway's managed
    # MySQL variables without needing to duplicate each value in its dashboard.
    MYSQL_HOST = os.getenv("MYSQL_HOST") or os.getenv("MYSQLHOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT") or os.getenv("MYSQLPORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER") or os.getenv("MYSQLUSER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQLPASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE") or os.getenv("MYSQLDATABASE", "inventory_db")
    LOW_STOCK_LIMIT = int(os.getenv("LOW_STOCK_LIMIT", "10"))
