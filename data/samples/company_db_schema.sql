-- QueryMate company database demo schema.
-- Run only against a disposable local/demo MySQL instance.
CREATE DATABASE IF NOT EXISTS company_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE company_db;

CREATE TABLE IF NOT EXISTS departments (
    department_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    department_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (department_id),
    UNIQUE KEY uq_departments_name (department_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS employees (
    employee_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    employee_name VARCHAR(120) NOT NULL,
    department_id INT UNSIGNED NOT NULL,
    salary DECIMAL(12, 2) NOT NULL,
    joining_date DATE NOT NULL,
    designation VARCHAR(100) NOT NULL,
    PRIMARY KEY (employee_id),
    KEY idx_employees_department (department_id),
    KEY idx_employees_salary (salary),
    KEY idx_employees_joining_date (joining_date),
    KEY idx_employees_designation (designation),
    CONSTRAINT chk_employees_salary CHECK (salary >= 0),
    CONSTRAINT fk_employees_department FOREIGN KEY (department_id)
        REFERENCES departments (department_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS projects (
    project_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    project_name VARCHAR(160) NOT NULL,
    department_id INT UNSIGNED NOT NULL,
    start_date DATE NOT NULL,
    status ENUM('planned', 'active', 'on_hold', 'completed', 'cancelled') NOT NULL,
    PRIMARY KEY (project_id),
    KEY idx_projects_department (department_id),
    KEY idx_projects_status (status),
    KEY idx_projects_start_date (start_date),
    CONSTRAINT fk_projects_department FOREIGN KEY (department_id)
        REFERENCES departments (department_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS attendance (
    attendance_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    employee_id INT UNSIGNED NOT NULL,
    attendance_date DATE NOT NULL,
    status ENUM('present', 'absent', 'late', 'remote', 'holiday') NOT NULL,
    PRIMARY KEY (attendance_id),
    UNIQUE KEY uq_attendance_employee_date (employee_id, attendance_date),
    KEY idx_attendance_date_status (attendance_date, status),
    CONSTRAINT fk_attendance_employee FOREIGN KEY (employee_id)
        REFERENCES employees (employee_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS leaves (
    leave_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    employee_id INT UNSIGNED NOT NULL,
    leave_type ENUM('annual', 'sick', 'personal', 'parental', 'unpaid') NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    leave_status ENUM('pending', 'approved', 'rejected', 'cancelled') NOT NULL,
    PRIMARY KEY (leave_id),
    KEY idx_leaves_employee (employee_id),
    KEY idx_leaves_dates (start_date, end_date),
    KEY idx_leaves_status (leave_status),
    CONSTRAINT chk_leaves_date_order CHECK (end_date >= start_date),
    CONSTRAINT fk_leaves_employee FOREIGN KEY (employee_id)
        REFERENCES employees (employee_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;
