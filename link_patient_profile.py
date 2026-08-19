"""
link_patient_profile.py

For accounts that registered BEFORE the fix that auto-creates a patient
profile on signup. If you're a patient and get "We couldn't find a patient
profile linked to your account yet" when booking an appointment, run this
once to fix your account.

Usage:
    cd project/backend        (the folder that has run.py and .env)
    python link_patient_profile.py
"""
import os

import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "hospital_db")


def get_connection():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )


def main():
    email = input("Enter the patient's login email: ").strip()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    if not user:
        print(f"No user found with email '{email}'. Check the spelling and try again.")
        return

    if user["role"] != "patient":
        print(f"This account has role '{user['role']}', not 'patient' — nothing to link.")
        return

    cur.execute("SELECT * FROM patients WHERE user_id = %s", (user["id"],))
    existing = cur.fetchone()
    if existing:
        print(f"This account already has a linked patient profile (patient id: {existing['id']}). Nothing to do.")
        return

    cur.execute(
        "INSERT INTO patients (user_id, first_name, last_name, phone, email) VALUES (%s, %s, %s, %s, %s)",
        (user["id"], user["first_name"], user["last_name"], user["phone"], user["email"]),
    )
    patient_id = cur.lastrowid

    print(f"Done! Linked a new patient profile (id: {patient_id}) to '{email}'.")
    print("You can now log in and book an appointment. You can also fill in the")
    print("rest of your medical details (allergies, insurance, etc.) later from the app.")

    conn.close()


if __name__ == "__main__":
    main()
