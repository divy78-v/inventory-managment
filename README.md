# StockPilot — Inventory Management System

StockPilot is a college-level Inventory Management System built with Python Flask, MySQL, Bootstrap, HTML, CSS, and JavaScript. It is intentionally organised with simple, readable code so it is easy to explain in a viva.

## Features

- Secure login and logout using hashed passwords
- Dashboard with total products, total stock, stock value, low-stock alerts, and recent activity
- Product add, edit, archive, search, category filtering, prices, and reorder levels
- Category and supplier add, edit, and safe deletion checks
- Manual Stock In / Stock Out with a complete movement history
- Purchase records that increase stock automatically
- Sales records that reduce stock automatically and prevent negative stock
- Printable purchase records and customer invoices
- Date-range sales/purchase reports, top-selling products, low-stock report, and CSV exports
- Responsive interface for desktop and mobile

## Project structure

```text
inventory-management-system/
├── app.py                  # Creates the Flask app and registers blueprints
├── config.py               # MySQL and Flask configuration
├── database.py             # MySQL connection, schema creation, starter data
├── auth.py                 # Login and logout routes
├── inventory.py            # Dashboard, products, stock, purchases, sales
├── reports.py              # On-screen reports and CSV downloads
├── utils.py                # Login protection and Indian currency formatter
├── schema.sql              # Complete MySQL table structure
├── requirements.txt        # Python packages
├── .env.example            # Configuration template
├── static/
│   ├── css/style.css       # Responsive custom styling
│   └── js/main.js          # Sidebar, confirmation and line-item interactions
└── templates/
    ├── auth/               # Login screen
    ├── products/           # Product list and form
    ├── categories/         # Category management
    ├── suppliers/          # Supplier management
    ├── stock/              # Stock In / Out screen
    ├── purchases/          # Purchase records and printable record
    ├── sales/              # Sales records and printable invoice
    ├── reports/            # Report screen
    ├── errors/             # 404 page
    ├── base.html           # Shared dashboard layout
    └── dashboard.html
```

## Database design

The system uses these linked tables:

| Table | Purpose |
| --- | --- |
| `users` | Login account details and password hash |
| `categories` | Product groups such as Beverages and Electronics |
| `suppliers` | Vendor contact details |
| `products` | Product master, prices, live stock, and reorder level |
| `stock_movements` | Audit trail for every change in quantity |
| `purchases` / `purchase_items` | Purchase header and its multiple product lines |
| `sales` / `sale_items` | Invoice header and its multiple product lines |

`purchase_items` and `sale_items` are separate from their main records because one purchase or invoice can contain many products. The application updates both `products.current_stock` and `stock_movements` inside the same MySQL transaction, so a half-saved sale or purchase is rolled back when an error happens.

## Setup (step by step)

### 1. Install prerequisites

- Python 3.10 or later
- MySQL Server 8.0 or later (or compatible MariaDB)
- `pip`

### 2. Open the project folder

```bash
cd "/Users/divyvaghani/Documents/New project/inventory-management-system"
```

### 3. Create and activate a virtual environment

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 4. Install Python packages

```bash
pip install -r requirements.txt
```

### 5. Configure MySQL

Make sure the MySQL server is running. Copy `.env.example` to a new file called `.env`, then update the password and user values.

```bash
cp .env.example .env
```

Example `.env` for a local MySQL installation:

```env
SECRET_KEY=my-local-college-project-secret
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=inventory_db
```

If your MySQL user cannot create databases, first run this in MySQL Workbench or the MySQL terminal:

```sql
CREATE DATABASE inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The complete SQL schema is in [`schema.sql`](schema.sql). Normally you do not have to run it manually because the next command does it for you.

### 6. Create tables and sample data

```bash
flask --app app init-db
```

This command safely creates the database/tables if they do not already exist and adds:

- Admin user: `admin`
- Password: `admin123`
- Realistic categories, suppliers, and six products
- Opening stock movements

Change the demo password before using the project beyond a classroom demo.

### 7. Run the project

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser and sign in with the demo credentials.

## How the main workflows work

1. **Add a product**: Product details and opening quantity are saved. An `OPENING` row is also added to `stock_movements`.
2. **Stock In / Out**: The app locks the selected product while changing quantity. Stock Out is rejected when there is insufficient stock.
3. **Purchase**: A purchase header and multiple `purchase_items` rows are saved. Each item increases current stock and gets a `PURCHASE` movement.
4. **Sale**: Before saving, the app checks every selected product's available quantity. It then creates the invoice, sale items, and `SALE` movements, while decreasing current stock.
5. **Low-stock alert**: Any active product with `current_stock <= reorder_level` appears in the dashboard, products page, and reports.

## Useful MySQL checks

Open MySQL and select the database:

```sql
USE inventory_db;
SELECT id, name, sku, current_stock, reorder_level FROM products;
SELECT * FROM stock_movements ORDER BY created_at DESC;
SELECT invoice_number, customer_name, total_amount FROM sales;
```

## Production notes

For a real deployment, use a strong random `SECRET_KEY`, a non-root MySQL account with limited permissions, HTTPS, CSRF protection (for example Flask-WTF), backups, and a proper tax/GST configuration. The current version is designed as an understandable and fully working college project.

For the Railway deployment procedure, see [`DEPLOYMENT.md`](DEPLOYMENT.md).
