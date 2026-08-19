-- =========================================================
-- Hospital Management System — Full Database Schema
-- MySQL 8.0+
-- Run this once on a fresh database:  mysql -u root -p hospital_db < docs/schema.sql
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone           VARCHAR(20)  NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            ENUM('super_admin','hospital_admin','doctor','receptionist',
                          'pharmacist','lab_technician','cashier','patient') NOT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    last_login_at   DATETIME     NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS token_blocklist (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    jti         VARCHAR(64)  NOT NULL UNIQUE,
    user_id     INT          NOT NULL,
    expires_at  DATETIME     NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS departments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL UNIQUE,
    description VARCHAR(255) NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS doctors (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    department_id   INT NULL,
    specialty       VARCHAR(150) NULL,
    qualification   VARCHAR(150) NULL,
    experience_years INT NULL,
    consultation_fee DECIMAL(10,2) NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS doctor_availability (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id   INT NOT NULL,
    day_of_week ENUM('mon','tue','wed','thu','fri','sat','sun') NOT NULL,
    start_time  TIME NOT NULL,
    end_time    TIME NOT NULL,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS patients (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NULL,
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    date_of_birth       DATE NULL,
    gender              ENUM('male','female','other') NULL,
    phone               VARCHAR(20) NULL,
    email               VARCHAR(150) NULL,
    address             VARCHAR(255) NULL,
    blood_group         VARCHAR(5) NULL,
    allergies           TEXT NULL,
    medical_history     TEXT NULL,
    emergency_contact_name  VARCHAR(150) NULL,
    emergency_contact_phone VARCHAR(20) NULL,
    insurance_provider  VARCHAR(150) NULL,
    insurance_policy_no VARCHAR(100) NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS appointments (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    patient_id    INT NOT NULL,
    doctor_id     INT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status        ENUM('pending','approved','rejected','cancelled','rescheduled','completed') NOT NULL DEFAULT 'pending',
    queue_number  INT NULL,
    reason        VARCHAR(255) NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS consultation_notes (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id INT NOT NULL,
    doctor_id      INT NOT NULL,
    patient_id     INT NOT NULL,
    symptoms       TEXT NULL,
    diagnosis      TEXT NULL,
    notes          TEXT NULL,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prescriptions (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id INT NULL,
    doctor_id      INT NOT NULL,
    patient_id     INT NOT NULL,
    notes          VARCHAR(255) NULL,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prescription_items (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id  INT NOT NULL,
    medicine_name    VARCHAR(150) NOT NULL,
    dosage           VARCHAR(100) NULL,
    frequency        VARCHAR(100) NULL,
    duration         VARCHAR(100) NULL,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS medical_records (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    patient_id   INT NOT NULL,
    title        VARCHAR(150) NOT NULL,
    file_url     VARCHAR(500) NOT NULL,   -- Cloudinary URL
    file_type    VARCHAR(10) NOT NULL,     -- pdf / png / jpg
    uploaded_by  INT NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS lab_tests (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    patient_id    INT NOT NULL,
    doctor_id     INT NULL,
    test_name     VARCHAR(150) NOT NULL,
    status        ENUM('requested','in_progress','completed','cancelled') NOT NULL DEFAULT 'requested',
    report_url    VARCHAR(500) NULL,
    requested_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at  DATETIME NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS medicines (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(150) NOT NULL,
    category      VARCHAR(100) NULL,
    unit_price    DECIMAL(10,2) NOT NULL DEFAULT 0,
    stock_qty     INT NOT NULL DEFAULT 0,
    low_stock_threshold INT NOT NULL DEFAULT 10,
    expiry_date   DATE NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pharmacy_sales (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id   INT NOT NULL,
    patient_id    INT NULL,
    quantity      INT NOT NULL,
    total_price   DECIMAL(10,2) NOT NULL,
    sold_by       INT NULL,
    sold_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL,
    FOREIGN KEY (sold_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS suppliers (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    phone       VARCHAR(20) NULL,
    email       VARCHAR(150) NULL,
    address     VARCHAR(255) NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_orders (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id  INT NOT NULL,
    item_name    VARCHAR(150) NOT NULL,
    quantity     INT NOT NULL,
    unit_price   DECIMAL(10,2) NOT NULL,
    status       ENUM('pending','received','cancelled') NOT NULL DEFAULT 'pending',
    ordered_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    received_at  DATETIME NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stock_movements (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    item_name    VARCHAR(150) NOT NULL,
    movement_type ENUM('in','out') NOT NULL,
    quantity     INT NOT NULL,
    reason       VARCHAR(255) NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS invoices (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    patient_id     INT NOT NULL,
    subtotal       DECIMAL(10,2) NOT NULL DEFAULT 0,
    tax_amount     DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount   DECIMAL(10,2) NOT NULL DEFAULT 0,
    payment_method ENUM('cash','card','insurance','online') NULL,
    status         ENUM('unpaid','paid','partially_paid','cancelled') NOT NULL DEFAULT 'unpaid',
    pdf_url        VARCHAR(500) NULL,
    created_by     INT NULL,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS invoice_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    invoice_id  INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    quantity    INT NOT NULL DEFAULT 1,
    unit_price  DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS beds (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    ward_name   VARCHAR(100) NOT NULL,
    bed_number  VARCHAR(20) NOT NULL,
    status      ENUM('available','occupied','maintenance') NOT NULL DEFAULT 'available',
    UNIQUE KEY unique_ward_bed (ward_name, bed_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admissions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    patient_id    INT NOT NULL,
    bed_id        INT NOT NULL,
    doctor_id     INT NULL,
    admitted_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    discharged_at DATETIME NULL,
    reason        VARCHAR(255) NULL,
    status        ENUM('admitted','discharged') NOT NULL DEFAULT 'admitted',
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (bed_id) REFERENCES beds(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS emergency_patients (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    full_name     VARCHAR(150) NOT NULL,
    age           INT NULL,
    gender        ENUM('male','female','other') NULL,
    condition_note TEXT NULL,
    severity      ENUM('low','medium','high','critical') NOT NULL DEFAULT 'medium',
    status        ENUM('waiting','in_treatment','admitted','discharged') NOT NULL DEFAULT 'waiting',
    brought_by    VARCHAR(150) NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notifications (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    title       VARCHAR(150) NOT NULL,
    message     TEXT NOT NULL,
    is_read     TINYINT(1) NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NULL,
    action      VARCHAR(150) NOT NULL,
    entity_type VARCHAR(100) NULL,
    entity_id   VARCHAR(50) NULL,
    details     VARCHAR(500) NULL,
    ip_address  VARCHAR(45) NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
