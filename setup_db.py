"""
setup_db.py

Run this once to set up the database — no need for the `mysql` command-line
tool or editing your PATH. It uses PyMySQL directly (already in
requirements.txt).

What it does:
  1. Reads docs/schema.sql and creates all the tables.
  2. Asks you for a Super Admin and Hospital Admin email/password,
     hashes the passwords with bcrypt, and inserts those two users.

Usage:
    cd project/backend        (the folder that has run.py and .env)
    python setup_db.py
"""
import os
import re
import getpass

import pymysql
import pymysql.cursors
import bcrypt
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "hospital_db")

SCHEMA_PATH = os.path.join("docs", "schema.sql")


def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def run_schema(conn):
    print(f"Reading {SCHEMA_PATH} ...")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql_text = f.read()

    # Remove SQL comments (lines starting with --) then split on semicolons.
    sql_text = re.sub(r"--.*", "", sql_text)
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]

    with conn.cursor() as cursor:
        for i, statement in enumerate(statements, start=1):
            cursor.execute(statement)
            print(f"  [{i}/{len(statements)}] OK")

    print(f"Schema applied successfully — {len(statements)} statements executed.\n")


def create_admin_user(conn, role_label, role_value):
    print(f"--- Create {role_label} account ---")
    first_name = input("First name: ").strip() or "System"
    last_name = input("Last name: ").strip() or "Admin"
    email = input("Email: ").strip()
    phone = input("Phone (optional): ").strip() or None
    password = getpass.getpass("Password: ")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO users (first_name, last_name, email, phone, password_hash, role, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            """,
            (first_name, last_name, email, phone, password_hash, role_value),
        )
    print(f"{role_label} account created: {email}\n")


def main():
    print(f"Connecting to MySQL database '{DB_NAME}' on {DB_HOST}:{DB_PORT} as '{DB_USER}' ...")
    conn = get_connection()
    print("Connected.\n")

    run_schema(conn)

    if input("Create a Super Admin account now? (y/n): ").strip().lower() == "y":
        create_admin_user(conn, "Super Admin", "super_admin")

    if input("Create a Hospital Admin account now? (y/n): ").strip().lower() == "y":
        create_admin_user(conn, "Hospital Admin", "hospital_admin")

    conn.close()
    print("Done! You can now start the backend with: python run.py")


if __name__ == "__main__":
    main()
