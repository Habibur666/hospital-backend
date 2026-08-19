"""
seed_data.py

Fills the database with realistic sample data across every module, so you
can click around the whole system (Patients, Appointments, Prescriptions,
Lab, Pharmacy, Inventory, Billing, Admissions, Emergency, Notifications...)
without manually creating everything by hand first.

Run this AFTER setup_db.py (i.e. after the schema exists and you've created
your Super Admin / Hospital Admin accounts).

Usage:
    cd project/backend        (the folder that has run.py and .env)
    python seed_data.py

Safe to re-run: it checks for existing rows (by unique fields like email /
medicine name / department name) and skips them instead of erroring out.

All seeded staff/patient accounts use this password:  Passw0rd!
"""
import os
from datetime import date, timedelta

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

SEED_PASSWORD = "Passw0rd!"
TODAY = date.today()


def get_connection():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_or_create_user(cur, first_name, last_name, email, phone, role):
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        """INSERT INTO users (first_name, last_name, email, phone, password_hash, role, is_active)
           VALUES (%s, %s, %s, %s, %s, %s, 1)""",
        (first_name, last_name, email, phone, hash_password(SEED_PASSWORD), role),
    )
    return cur.lastrowid


def get_or_create_department(cur, name, description):
    cur.execute("SELECT id FROM departments WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO departments (name, description) VALUES (%s, %s)", (name, description))
    return cur.lastrowid


def get_or_create_doctor(cur, user_id, department_id, specialty, qualification, years, fee):
    cur.execute("SELECT id FROM doctors WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        """INSERT INTO doctors (user_id, department_id, specialty, qualification, experience_years, consultation_fee)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, department_id, specialty, qualification, years, fee),
    )
    return cur.lastrowid


def get_or_create_patient(cur, user_id, first_name, last_name, dob, gender, phone, email,
                           address, blood_group, allergies, history, ec_name, ec_phone,
                           insurer, policy_no):
    cur.execute("SELECT id FROM patients WHERE first_name=%s AND last_name=%s AND phone=%s",
                (first_name, last_name, phone))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        """INSERT INTO patients
           (user_id, first_name, last_name, date_of_birth, gender, phone, email, address,
            blood_group, allergies, medical_history, emergency_contact_name,
            emergency_contact_phone, insurance_provider, insurance_policy_no)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (user_id, first_name, last_name, dob, gender, phone, email, address, blood_group,
         allergies, history, ec_name, ec_phone, insurer, policy_no),
    )
    return cur.lastrowid


def main():
    print(f"Connecting to '{DB_NAME}' on {DB_HOST}:{DB_PORT} ...")
    conn = get_connection()
    cur = conn.cursor()
    print("Connected.\n")

    # ---------------- Departments ----------------
    print("Seeding departments ...")
    dept_cardiology = get_or_create_department(cur, "Cardiology", "Heart and cardiovascular care")
    dept_general = get_or_create_department(cur, "General Medicine", "General checkups and internal medicine")
    dept_ortho = get_or_create_department(cur, "Orthopedics", "Bones, joints and muscles")
    dept_peds = get_or_create_department(cur, "Pediatrics", "Child healthcare")

    # ---------------- Staff users + doctor profiles ----------------
    print("Seeding staff accounts ...")
    doc1_user = get_or_create_user(cur, "Rafiq", "Islam", "dr.rafiq@hospital.com", "01710000001", "doctor")
    doc2_user = get_or_create_user(cur, "Nusrat", "Jahan", "dr.nusrat@hospital.com", "01710000002", "doctor")
    doc3_user = get_or_create_user(cur, "Kamal", "Hossain", "dr.kamal@hospital.com", "01710000003", "doctor")

    doctor1 = get_or_create_doctor(cur, doc1_user, dept_cardiology, "Cardiologist", "MBBS, MD (Cardiology)", 12, 1500.00)
    doctor2 = get_or_create_doctor(cur, doc2_user, dept_general, "General Physician", "MBBS", 6, 800.00)
    doctor3 = get_or_create_doctor(cur, doc3_user, dept_ortho, "Orthopedic Surgeon", "MBBS, MS (Ortho)", 9, 1200.00)

    receptionist_user = get_or_create_user(cur, "Shirin", "Akter", "reception@hospital.com", "01710000010", "receptionist")
    pharmacist_user = get_or_create_user(cur, "Tanvir", "Ahmed", "pharmacist@hospital.com", "01710000011", "pharmacist")
    lab_tech_user = get_or_create_user(cur, "Farida", "Yasmin", "labtech@hospital.com", "01710000012", "lab_technician")
    cashier_user = get_or_create_user(cur, "Mizanur", "Rahman", "cashier@hospital.com", "01710000013", "cashier")

    # ---------------- Patient user accounts + profiles ----------------
    print("Seeding patients ...")
    patient1_user = get_or_create_user(cur, "Abdul", "Karim", "karim.patient@example.com", "01810000001", "patient")
    patient2_user = get_or_create_user(cur, "Sultana", "Begum", "sultana.patient@example.com", "01810000002", "patient")

    patient1 = get_or_create_patient(
        cur, patient1_user, "Abdul", "Karim", date(1985, 4, 12), "male", "01810000001",
        "karim.patient@example.com", "House 12, Road 5, Dhanmondi, Dhaka", "O+",
        "Penicillin", "Hypertension, diagnosed 2019", "Rahim Karim", "01810000099",
        "Green Delta Insurance", "GDI-88231",
    )
    patient2 = get_or_create_patient(
        cur, patient2_user, "Sultana", "Begum", date(1992, 9, 3), "female", "01810000002",
        "sultana.patient@example.com", "House 4, Road 2, Uttara, Dhaka", "A+",
        "None known", "No major history", "Kabir Begum", "01810000098",
        None, None,
    )
    patient3 = get_or_create_patient(
        cur, None, "Jamal", "Uddin", date(1970, 1, 20), "male", "01910000003",
        "jamal.walkin@example.com", "Mirpur 10, Dhaka", "B+",
        "Aspirin", "Diabetic (Type 2)", "Nazma Uddin", "01910000097",
        None, None,
    )

    # ---------------- Appointments ----------------
    print("Seeding appointments ...")
    def create_appointment(patient_id, doctor_id, when, when_time, status, reason, queue):
        cur.execute(
            "SELECT id FROM appointments WHERE patient_id=%s AND doctor_id=%s AND appointment_date=%s AND appointment_time=%s",
            (patient_id, doctor_id, when, when_time),
        )
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute(
            """INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, status, queue_number, reason)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (patient_id, doctor_id, when, when_time, status, queue, reason),
        )
        return cur.lastrowid

    appt1 = create_appointment(patient1, doctor1, TODAY, "10:00:00", "approved", "Chest pain and shortness of breath", 1)
    appt2 = create_appointment(patient2, doctor2, TODAY, "11:30:00", "pending", "Annual checkup", 2)
    appt3 = create_appointment(patient3, doctor3, TODAY + timedelta(days=1), "09:00:00", "pending", "Knee pain", 1)
    appt4 = create_appointment(patient1, doctor1, TODAY - timedelta(days=7), "10:00:00", "completed", "Follow-up: blood pressure", 1)

    # ---------------- Consultation notes ----------------
    print("Seeding consultation notes ...")
    cur.execute("SELECT id FROM consultation_notes WHERE appointment_id=%s", (appt4,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO consultation_notes (appointment_id, doctor_id, patient_id, symptoms, diagnosis, notes)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (appt4, doctor1, patient1, "Elevated blood pressure, mild headache",
             "Stage 1 Hypertension", "Advised low-sodium diet, follow up in 4 weeks."),
        )

    # ---------------- Prescriptions + items ----------------
    print("Seeding prescriptions ...")
    cur.execute("SELECT id FROM prescriptions WHERE appointment_id=%s", (appt4,))
    row = cur.fetchone()
    if row:
        rx1 = row["id"]
    else:
        cur.execute(
            "INSERT INTO prescriptions (appointment_id, doctor_id, patient_id, notes) VALUES (%s,%s,%s,%s)",
            (appt4, doctor1, patient1, "Take medication after meals. Recheck BP in 2 weeks."),
        )
        rx1 = cur.lastrowid
        cur.executemany(
            "INSERT INTO prescription_items (prescription_id, medicine_name, dosage, frequency, duration) VALUES (%s,%s,%s,%s,%s)",
            [
                (rx1, "Amlodipine", "5mg", "Once daily", "30 days"),
                (rx1, "Losartan", "50mg", "Once daily", "30 days"),
            ],
        )

    # ---------------- Medical records ----------------
    print("Seeding medical records ...")
    cur.execute("SELECT id FROM medical_records WHERE patient_id=%s", (patient1,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO medical_records (patient_id, title, file_url, file_type, uploaded_by)
               VALUES (%s,%s,%s,%s,%s)""",
            (patient1, "ECG Report - Jan 2026",
             "https://res.cloudinary.com/demo/image/upload/sample.pdf", "pdf", doc1_user),
        )

    # ---------------- Lab tests ----------------
    print("Seeding lab tests ...")
    cur.execute("SELECT id FROM lab_tests WHERE patient_id=%s AND test_name=%s", (patient1, "Lipid Profile"))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO lab_tests (patient_id, doctor_id, test_name, status) VALUES (%s,%s,%s,%s)",
            (patient1, doctor1, "Lipid Profile", "requested"),
        )
    cur.execute("SELECT id FROM lab_tests WHERE patient_id=%s AND test_name=%s", (patient2, "Complete Blood Count"))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO lab_tests (patient_id, doctor_id, test_name, status) VALUES (%s,%s,%s,%s)",
            (patient2, doctor2, "Complete Blood Count", "completed"),
        )

    # ---------------- Medicines ----------------
    print("Seeding medicines ...")
    def get_or_create_medicine(name, category, price, stock, threshold, expiry):
        cur.execute("SELECT id FROM medicines WHERE name = %s", (name,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute(
            """INSERT INTO medicines (name, category, unit_price, stock_qty, low_stock_threshold, expiry_date)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (name, category, price, stock, threshold, expiry),
        )
        return cur.lastrowid

    med_paracetamol = get_or_create_medicine("Paracetamol 500mg", "Analgesic", 2.50, 500, 50, TODAY + timedelta(days=400))
    med_amoxicillin = get_or_create_medicine("Amoxicillin 250mg", "Antibiotic", 5.00, 8, 20, TODAY + timedelta(days=20))
    med_amlodipine = get_or_create_medicine("Amlodipine 5mg", "Antihypertensive", 3.20, 200, 30, TODAY + timedelta(days=300))
    med_losartan = get_or_create_medicine("Losartan 50mg", "Antihypertensive", 4.10, 150, 30, TODAY + timedelta(days=250))
    med_insulin = get_or_create_medicine("Insulin Glargine", "Antidiabetic", 350.00, 5, 10, TODAY + timedelta(days=15))

    # ---------------- Pharmacy sales ----------------
    print("Seeding pharmacy sales ...")
    cur.execute("SELECT id FROM pharmacy_sales WHERE medicine_id=%s AND patient_id=%s", (med_amlodipine, patient1))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO pharmacy_sales (medicine_id, patient_id, quantity, total_price, sold_by) VALUES (%s,%s,%s,%s,%s)",
            (med_amlodipine, patient1, 30, 30 * 3.20, pharmacist_user),
        )

    # ---------------- Suppliers + purchase orders + stock movements ----------------
    print("Seeding inventory (suppliers, purchase orders, stock movements) ...")
    def get_or_create_supplier(name, phone, email, address):
        cur.execute("SELECT id FROM suppliers WHERE name = %s", (name,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO suppliers (name, phone, email, address) VALUES (%s,%s,%s,%s)",
                    (name, phone, email, address))
        return cur.lastrowid

    supplier1 = get_or_create_supplier("MediSupply Ltd.", "0288000001", "sales@medisupply.example", "Tejgaon, Dhaka")
    supplier2 = get_or_create_supplier("HealthCare Distributors", "0288000002", "info@hcd.example", "Chattogram")

    cur.execute("SELECT id FROM purchase_orders WHERE supplier_id=%s AND item_name=%s", (supplier1, "Amoxicillin 250mg"))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO purchase_orders (supplier_id, item_name, quantity, unit_price, status) VALUES (%s,%s,%s,%s,%s)",
            (supplier1, "Amoxicillin 250mg", 200, 4.50, "pending"),
        )

    cur.execute("SELECT id FROM stock_movements WHERE item_name=%s LIMIT 1", ("Paracetamol 500mg",))
    if not cur.fetchone():
        cur.executemany(
            "INSERT INTO stock_movements (item_name, movement_type, quantity, reason) VALUES (%s,%s,%s,%s)",
            [
                ("Paracetamol 500mg", "in", 500, "Initial stock"),
                ("Amoxicillin 250mg", "out", 12, "Dispensed to patients"),
            ],
        )

    # ---------------- Billing ----------------
    print("Seeding invoices ...")
    cur.execute("SELECT id FROM invoices WHERE patient_id=%s", (patient1,))
    if not cur.fetchone():
        subtotal = 1500.00 + (30 * 3.20)
        tax = round(subtotal * 0.05, 2)
        total = subtotal + tax
        cur.execute(
            """INSERT INTO invoices (patient_id, subtotal, tax_amount, discount_amount, total_amount, payment_method, status, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (patient1, subtotal, tax, 0, total, "cash", "unpaid", cashier_user),
        )
        invoice1 = cur.lastrowid
        cur.executemany(
            "INSERT INTO invoice_items (invoice_id, description, quantity, unit_price) VALUES (%s,%s,%s,%s)",
            [
                (invoice1, "Cardiology Consultation", 1, 1500.00),
                (invoice1, "Amlodipine 5mg (30 tablets)", 30, 3.20),
            ],
        )

    # ---------------- Beds + admissions ----------------
    print("Seeding beds and admissions ...")
    def get_or_create_bed(ward, number, status="available"):
        cur.execute("SELECT id FROM beds WHERE ward_name=%s AND bed_number=%s", (ward, number))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO beds (ward_name, bed_number, status) VALUES (%s,%s,%s)", (ward, number, status))
        return cur.lastrowid

    bed1 = get_or_create_bed("General Ward", "G-101", "available")
    bed2 = get_or_create_bed("General Ward", "G-102", "available")
    bed3 = get_or_create_bed("ICU", "ICU-1", "occupied")
    get_or_create_bed("ICU", "ICU-2", "available")
    get_or_create_bed("Pediatric Ward", "P-201", "available")

    cur.execute("SELECT id FROM admissions WHERE bed_id=%s AND status='admitted'", (bed3,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO admissions (patient_id, bed_id, doctor_id, reason, status) VALUES (%s,%s,%s,%s,%s)",
            (patient3, bed3, doctor3, "Post-surgery observation", "admitted"),
        )

    # ---------------- Emergency patients ----------------
    print("Seeding emergency patients ...")
    cur.execute("SELECT id FROM emergency_patients WHERE full_name=%s", ("Rina Aktar",))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO emergency_patients (full_name, age, gender, condition_note, severity, status, brought_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            ("Rina Aktar", 34, "female", "Road traffic accident, suspected fracture", "high", "waiting", "Family member"),
        )

    # ---------------- Notifications ----------------
    print("Seeding notifications ...")
    cur.execute("SELECT id FROM notifications WHERE user_id=%s AND title=%s", (doc1_user, "New appointment booked"))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO notifications (user_id, title, message) VALUES (%s,%s,%s)",
            (doc1_user, "New appointment booked", "Abdul Karim booked an appointment with you for today at 10:00 AM."),
        )

    conn.close()
    print("\nDone! Sample data has been seeded.")
    print(f"All seeded staff/patient accounts use the password: {SEED_PASSWORD}")
    print("Staff logins: dr.rafiq@hospital.com, dr.nusrat@hospital.com, dr.kamal@hospital.com,")
    print("              reception@hospital.com, pharmacist@hospital.com, labtech@hospital.com, cashier@hospital.com")
    print("Patient logins: karim.patient@example.com, sultana.patient@example.com")


if __name__ == "__main__":
    main()
