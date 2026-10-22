# Deploying StockPilot to Railway

This project includes a `Dockerfile`, so Railway uses the same production start command on every deployment.

## 1. Publish the project

Create a GitHub repository containing the contents of this `inventory-management-system` folder. Do not commit `.env`; it is ignored by Git.

## 2. Create Railway services

1. Create a new Railway project.
2. Add **MySQL** from **New**.
3. Add **GitHub Repo** and select your repository. If this folder is inside a larger repository, set **Root Directory** to `inventory-management-system`.

The application accepts Railway's native `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, and `MYSQLDATABASE` variables automatically. Add only these application variables:

```text
SECRET_KEY=<a-long-random-value>
FLASK_DEBUG=0
```

## 3. Initialise tables and sample account

After the service and database are created, open a Railway shell for the Flask service and run:

```bash
flask --app app init-db
```

The command is safe to run again: it creates missing tables and does not replace existing records.

## 4. Make the app public

Open the Flask service, go to **Settings → Networking**, and choose **Generate Domain**. Open the generated URL and sign in with the demo account:

```text
Username: admin
Password: admin123
```

Change the demo password before handing the system to real users.
