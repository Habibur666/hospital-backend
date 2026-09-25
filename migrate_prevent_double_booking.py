"""
migrate_prevent_double_booking.py

Adds protection against two patients booking the same doctor at the same
date+time (a "race condition" — this can happen if two people submit a
booking within the same split second). This is enforced by MySQL itself
via a generated column + unique index, so it can never be bypassed no
matter how the request arrives.

Run this ONCE against a database that was set up BEFORE this fix existed
(e.g. your live Aiven database). If you're setting up a brand new database
with the current docs/schema.sql, you don't need this — it's already
included there.

Safe to re-run: it checks whether the column already exists first.

Usage:
    cd project/backend        (the folder that has run.py and .env)
    python migrate_prevent_double_booking.py
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
DB_SSL = os.getenv("DB_SSL", "false").lower() == "true"


def get_connection():
    connect_args = dict(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )
    if DB_SSL:
        connect_args["ssl"] = {"ssl": {}}
    return pymysql.connect(**connect_args)


def main():
    print(f"Connecting to '{DB_NAME}' on {DB_HOST}:{DB_PORT} ...")
    conn = get_connection()
    cur = conn.cursor()
    print("Connected.\n")

    cur.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'appointments' AND COLUMN_NAME = 'active_slot_key'
        """,
        (DB_NAME,),
    )
    already_done = cur.fetchone()["cnt"] > 0

    if already_done:
        print("Already applied — nothing to do.")
        conn.close()
        return

    print("Checking for existing double-bookings first (so the migration doesn't fail)...")
    cur.execute(
        """
        SELECT doctor_id, appointment_date, appointment_time, COUNT(*) AS cnt
        FROM appointments
        WHERE status NOT IN ('cancelled', 'rejected')
        GROUP BY doctor_id, appointment_date, appointment_time
        HAVING COUNT(*) > 1
        """
    )
    clashes = cur.fetchall()
    if clashes:
        print(f"Found {len(clashes)} existing double-booked slot(s):")
        for c in clashes:
            print(f"  doctor_id={c['doctor_id']}  {c['appointment_date']} {c['appointment_time']}  ({c['cnt']} appointments)")
        print(
            "\nYou'll need to resolve these manually first (cancel or reschedule the extra "
            "ones) — otherwise adding the new unique index below will fail. Run this script "
            "again once they're resolved."
        )
        conn.close()
        return

    print("No clashes found. Applying migration...")
    cur.execute(
        """
        ALTER TABLE appointments
        ADD COLUMN active_slot_key VARCHAR(60) GENERATED ALWAYS AS (
            CASE WHEN status IN ('cancelled', 'rejected') THEN NULL
            ELSE CONCAT(doctor_id, '_', appointment_date, '_', appointment_time)
            END
        ) STORED,
        ADD UNIQUE KEY uniq_active_appointment_slot (active_slot_key)
        """
    )
    print("Done! Double-booking is now prevented at the database level.")
    conn.close()


if __name__ == "__main__":
    main()
