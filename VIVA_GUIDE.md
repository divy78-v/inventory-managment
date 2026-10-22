# Viva Guide — StockPilot

Use these short explanations to present the project clearly.

## 1. What problem does this project solve?

It helps a small business keep product information, available stock, suppliers, purchases, and sales in one system. The business can see what is running low and avoid selling more items than it has.

## 2. Why Flask?

Flask is a lightweight Python web framework. It lets us create routes such as `/products` and `/sales/new`, receive form data, connect to MySQL, and return HTML templates. It is easier to understand than a large framework for a college project.

## 3. What is the role of each backend file?

- `app.py`: starts Flask, loads configuration, registers route modules, and adds the `init-db` command.
- `database.py`: creates/reuses a MySQL connection and inserts starter data.
- `auth.py`: verifies the login password and stores the logged-in user in the Flask session.
- `inventory.py`: contains the business logic for products, stock, purchases, and sales.
- `reports.py`: fetches date-range report data and produces downloadable CSV files.
- `utils.py`: contains reusable functions such as `login_required` and Indian currency formatting.

## 4. How is the password stored safely?

The password is not stored as plain text. `generate_password_hash()` converts `admin123` to a one-way password hash during setup. At login, `check_password_hash()` compares the entered password with that hash.

## 5. Why are there separate `sales` and `sale_items` tables?

A sale/invoice can contain multiple products. The `sales` table stores common invoice details such as customer, date, and total. `sale_items` stores one row for each product. This is a normalised database design and prevents repeating invoice data for every item.

The same design is used for `purchases` and `purchase_items`.

## 6. How is stock updated?

`products.current_stock` stores the current quantity for quick display. At the same time, `stock_movements` stores why the quantity changed (`OPENING`, `IN`, `OUT`, `PURCHASE`, or `SALE`). This gives both fast dashboard queries and a complete audit history.

## 7. How do you stop negative stock?

Before a sale or stock-out, the application reads the selected row using `FOR UPDATE`. This locks the product until the transaction finishes. It compares requested quantity with `current_stock`; if stock is insufficient, it raises an error and rolls back. So the quantity cannot go below zero.

## 8. What is a database transaction here?

A transaction groups related SQL statements. When saving a sale, the app creates the sale, inserts every sale item, reduces product stock, and adds stock movements. It calls `commit()` only after all of them work. If one fails, `rollback()` cancels every related change, keeping the database consistent.

## 9. How does the low-stock alert work?

Every product has a `reorder_level`. A SQL condition checks whether `current_stock <= reorder_level`. Matching products appear as alerts on the dashboard, products list, and reports page.

## 10. How are invoices and reports generated?

After a sale or purchase, Flask loads its header and line items into an HTML invoice template. The user can use the Print button and choose “Save as PDF” in the browser. The reports page runs date-range SQL queries and can export results as a CSV file, which opens in Excel.

## 11. What front-end technologies are used?

- HTML/Jinja templates make the page structure and insert database values.
- Bootstrap provides responsive grid, tables, forms, and buttons.
- Custom CSS creates the sidebar dashboard design and mobile layout.
- JavaScript adds/removes transaction lines, calculates totals in the browser, handles confirmations, and toggles the mobile navigation.

## 12. Possible improvements

- User roles and permissions (Admin, Manager, Cashier)
- GST number, tax slabs, and PDF generation on the server
- Product images and barcode scanning
- Pagination for very large inventories
- Supplier payment tracking and customer ledger
- Automated email/WhatsApp reorder notifications
