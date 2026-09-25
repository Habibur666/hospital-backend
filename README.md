# Hospital Management System — Backend

A complete Flask backend with **all 19 modules built together**, written in
a simple, beginner-friendly style. Database access uses **plain PyMySQL**
(direct connections, no ORM, no SQLAlchemy) with parameterized SQL queries.

## Stack
Python 3.10 · Flask · Flask Blueprints · **PyMySQL** (raw SQL, no ORM) ·
Flask-JWT-Extended · bcrypt · python-dotenv · Flask-CORS · Cloudinary
(file storage) · fpdf2 (PDF invoices)

## How the code is organized (kept simple on purpose)

```
project/
├── app/
│   ├── db.py            <- ALL database code lives here (PyMySQL helpers)
│   ├── config.py         <- settings, loaded from .env
│   ├── decorators.py     <- @login_required / @role_required
│   ├── helpers.py        <- ok()/fail() response helpers, pagination
│   ├── audit_log.py      <- log_action() used by every module
│   ├── auth/routes.py    <- register, login, logout, refresh
│   ├── users/routes.py
│   ├── departments/routes.py
│   ├── doctors/routes.py
│   ├── patients/routes.py
│   ├── appointments/routes.py
│   ├── consultations/routes.py
│   ├── prescriptions/routes.py
│   ├── medical_records/routes.py   <- Cloudinary uploads
│   ├── laboratory/routes.py        <- Cloudinary uploads
│   ├── pharmacy/routes.py
│   ├── inventory/routes.py
│   ├── billing/routes.py           <- PDF invoice generation
│   ├── admissions/routes.py
│   ├── emergency/routes.py
│   ├── reports/routes.py
│   ├── dashboard/routes.py
│   ├── notifications/routes.py     <- mock email sender
│   └── audit/routes.py             <- read-only audit log viewer
├── docs/schema.sql       <- run this once to create every table
├── uploads/               <- scratch folder (generated PDFs, etc.)
├── requirements.txt
└── run.py                 <- start here: python run.py
```

Each module is just **one `routes.py` file**. There's no separate
service/repository layer — every route talks straight to `app/db.py`
using plain SQL, which keeps things easy to read and follow. Every route
still:
- validates the request body,
- runs parameterized queries only (never string-formats SQL, so it's
  protected against SQL injection),
- returns the same `{success, message, data}` JSON shape,
- is protected with `@login_required` or `@role_required(...)`.

## Setup

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # fill in your real DB/Cloudinary/JWT secrets

# Create the database, then load every table in one go:
mysql -u root -p hospital_db < docs/schema.sql

python run.py
```

API runs at `http://localhost:5000`. Health check: `GET /health`.

## Roles (used by every `@role_required(...)` check)
`super_admin`, `hospital_admin`, `doctor`, `receptionist`, `pharmacist`,
`lab_technician`, `cashier`, `patient`

## Quick walkthrough of a typical flow

```bash
# 1. Register a hospital admin
POST /api/v1/auth/register
{ "first_name": "Ava", "last_name": "Admin", "email": "ava@hospital.com",
  "password": "Str0ng!Pass", "role": "hospital_admin" }

# 2. Log in to get tokens
POST /api/v1/auth/login
{ "email": "ava@hospital.com", "password": "Str0ng!Pass" }
-> returns { access_token, refresh_token, user }

# 3. Use the access token as a Bearer token on every other request
Authorization: Bearer <access_token>

# 4. Create a department, then a doctor user + doctor profile,
#    then a patient, then book an appointment, etc.
```

## Modules included (all 19, built together)

| # | Module | Notes |
|---|--------|-------|
| 1 | Authentication | register/login/logout/refresh, bcrypt + JWT |
| 2 | User Management | admin CRUD, activate/deactivate |
| 3 | Department Management | CRUD |
| 4 | Doctor Management | profile, availability, appointments, consultation history |
| 5 | Patient Management | profile, history, allergies, insurance, emergency contact |
| 6 | Appointment Management | book/cancel/reschedule/approve/reject/queue |
| 7 | Consultation Notes | symptoms/diagnosis/notes per appointment |
| 8 | Prescription Management | prescription + multiple medicine items |
| 9 | Medical Records | Cloudinary upload (PDF/PNG/JPG ≤0.5MB) + metadata |
| 10 | Laboratory | test requests, status, Cloudinary report upload |
| 11 | Pharmacy | stock, expiry, low-stock alerts, sales |
| 12 | Inventory | suppliers, stock in/out, purchase orders |
| 13 | Billing | invoice + tax + discount + payment + **PDF invoice** |
| 14 | Admission & Bed Management | beds, admit, discharge |
| 15 | Emergency Patients | intake + severity + status tracking |
| 16 | Reports | revenue, appointments, patients, pharmacy sales, doctor performance |
| 17 | Dashboard Analytics | today's numbers, 6-month chart data, department stats |
| 18 | Notifications | in-app + mock email sender (prints to console) |
| 19 | Audit Logs | every important action is logged automatically |

## Verified

The app factory (`create_app()`) was tested and imports cleanly with
**93 registered routes** across all 19 modules, and the health check /
validation error handling were smoke-tested successfully.

## Helper Scripts

| Script | What it does | When to run it |
|---|---|---|
| `setup_db.py` | Creates all tables from `docs/schema.sql`, then optionally creates a Super Admin / Hospital Admin account | Once, when setting up a brand new database |
| `seed_data.py` | Fills the database with realistic sample data (doctors, patients, appointments, medicines...) across every module | Optional, for demoing/testing |
| `link_patient_profile.py` | Links an existing patient login (created before the auto-link fix) to a patient profile | Only for accounts registered before that fix — new registrations link automatically |
| `migrate_prevent_double_booking.py` | Adds a database-level safeguard so two patients can never book the same doctor at the same date+time, even if both requests arrive at the same instant | Once, if your database was created before this fix existed — new databases already have it via `schema.sql` |

All scripts read the same `.env` file as the app and use plain PyMySQL — no `mysql` command-line tool required.

## Notes / what you'd still want before production
- Add a proper migrations tool (e.g. Alembic-style manual `.sql` migration
  files) instead of one big `schema.sql` as the project grows.
- Add rate limiting (Flask-Limiter) and full Swagger docs — left out here
  to keep the code beginner-friendly; ask if you'd like these added back.
- Add automated tests (pytest) for each module.
