-- Synthetic company records for natural-language-to-SQL demos.
-- Safe to re-run: explicit IDs and upserts keep this dataset repeatable.
USE company_db;

INSERT INTO departments (department_id, department_name) VALUES
    (1, 'Engineering'),
    (2, 'Human Resources'),
    (3, 'Finance'),
    (4, 'Sales'),
    (5, 'Marketing'),
    (6, 'Operations')
ON DUPLICATE KEY UPDATE department_name = VALUES(department_name);

INSERT INTO employees
    (employee_id, employee_name, department_id, salary, joining_date, designation)
VALUES
    (1, 'Ava Patel', 1, 118000.00, '2019-03-11', 'Engineering Manager'),
    (2, 'Liam Chen', 1, 97000.00, '2020-07-20', 'Senior Software Engineer'),
    (3, 'Mia Johnson', 1, 88000.00, '2021-01-18', 'Software Engineer'),
    (4, 'Noah Williams', 1, 82500.00, '2021-09-06', 'Data Engineer'),
    (5, 'Isabella Garcia', 1, 91000.00, '2022-02-14', 'Machine Learning Engineer'),
    (6, 'Ethan Brown', 1, 76000.00, '2022-06-27', 'QA Engineer'),
    (7, 'Sophia Davis', 1, 79000.00, '2023-04-10', 'Frontend Engineer'),
    (8, 'Mason Wilson', 1, 84000.00, '2023-08-21', 'DevOps Engineer'),
    (9, 'Charlotte Moore', 2, 105000.00, '2018-11-05', 'HR Director'),
    (10, 'Lucas Taylor', 2, 72000.00, '2020-04-13', 'HR Business Partner'),
    (11, 'Amelia Anderson', 2, 64500.00, '2021-07-12', 'Recruiter'),
    (12, 'James Thomas', 2, 61000.00, '2022-10-03', 'People Operations Specialist'),
    (13, 'Harper Jackson', 2, 68000.00, '2023-02-06', 'Learning and Development Specialist'),
    (14, 'Benjamin White', 3, 112000.00, '2018-06-18', 'Finance Director'),
    (15, 'Evelyn Harris', 3, 86000.00, '2019-12-02', 'Senior Accountant'),
    (16, 'Elijah Martin', 3, 73500.00, '2020-09-14', 'Financial Analyst'),
    (17, 'Abigail Thompson', 3, 71000.00, '2022-01-24', 'Accountant'),
    (18, 'Henry Robinson', 3, 78000.00, '2023-05-15', 'Budget Analyst'),
    (19, 'Emily Clark', 4, 108000.00, '2018-02-19', 'Sales Director'),
    (20, 'Alexander Lewis', 4, 82000.00, '2019-10-07', 'Account Executive'),
    (21, 'Elizabeth Walker', 4, 79500.00, '2020-05-25', 'Account Executive'),
    (22, 'Daniel Hall', 4, 69000.00, '2021-11-08', 'Sales Development Representative'),
    (23, 'Sofia Allen', 4, 87500.00, '2022-03-21', 'Key Account Manager'),
    (24, 'Michael Young', 4, 73500.00, '2023-06-12', 'Customer Success Manager'),
    (25, 'Ella Hernandez', 5, 99000.00, '2019-01-28', 'Marketing Director'),
    (26, 'Sebastian King', 5, 77000.00, '2020-08-17', 'Content Strategist'),
    (27, 'Avery Wright', 5, 81500.00, '2021-04-05', 'Digital Marketing Manager'),
    (28, 'Jack Lopez', 5, 66500.00, '2022-07-11', 'Marketing Analyst'),
    (29, 'Scarlett Hill', 5, 74000.00, '2023-09-18', 'Product Marketing Specialist'),
    (30, 'Owen Scott', 6, 103000.00, '2018-09-10', 'Operations Director'),
    (31, 'Grace Green', 6, 76000.00, '2020-02-24', 'Operations Analyst'),
    (32, 'Wyatt Adams', 6, 71000.00, '2021-06-07', 'Logistics Coordinator'),
    (33, 'Chloe Baker', 6, 68500.00, '2022-11-14', 'Facilities Manager'),
    (34, 'Leo Nelson', 6, 73500.00, '2024-01-08', 'Procurement Specialist'),
    (35, 'Lily Carter', 1, 92500.00, '2024-03-04', 'Security Engineer'),
    (36, 'Gabriel Mitchell', 4, 71000.00, '2024-05-20', 'Sales Development Representative')
ON DUPLICATE KEY UPDATE
    employee_name = VALUES(employee_name), department_id = VALUES(department_id),
    salary = VALUES(salary), joining_date = VALUES(joining_date), designation = VALUES(designation);

INSERT INTO projects (project_id, project_name, department_id, start_date, status) VALUES
    (1, 'Customer Data Platform', 1, '2024-02-01', 'active'),
    (2, 'Mobile App Modernization', 1, '2024-06-15', 'active'),
    (3, 'Security Readiness Program', 1, '2025-01-10', 'planned'),
    (4, 'Leadership Development', 2, '2024-03-01', 'active'),
    (5, 'Hiring Process Refresh', 2, '2024-09-12', 'completed'),
    (6, 'Annual Planning Cycle', 3, '2024-10-01', 'completed'),
    (7, 'Expense Automation', 3, '2025-02-03', 'active'),
    (8, 'Enterprise Accounts Expansion', 4, '2024-01-15', 'active'),
    (9, 'Customer Retention Initiative', 4, '2024-07-08', 'on_hold'),
    (10, 'Brand Awareness Campaign', 5, '2024-04-22', 'completed'),
    (11, 'Product Launch Northstar', 5, '2025-01-20', 'active'),
    (12, 'Warehouse Efficiency', 6, '2024-05-06', 'active')
ON DUPLICATE KEY UPDATE
    project_name = VALUES(project_name), department_id = VALUES(department_id),
    start_date = VALUES(start_date), status = VALUES(status);

INSERT INTO attendance (attendance_id, employee_id, attendance_date, status) VALUES
    (1, 1, '2025-03-03', 'present'), (2, 2, '2025-03-03', 'remote'),
    (3, 3, '2025-03-03', 'present'), (4, 4, '2025-03-03', 'late'),
    (5, 5, '2025-03-03', 'present'), (6, 6, '2025-03-03', 'absent'),
    (7, 7, '2025-03-03', 'present'), (8, 8, '2025-03-03', 'remote'),
    (9, 9, '2025-03-03', 'present'), (10, 10, '2025-03-03', 'present'),
    (11, 11, '2025-03-03', 'late'), (12, 12, '2025-03-03', 'present'),
    (13, 13, '2025-03-03', 'remote'), (14, 14, '2025-03-03', 'present'),
    (15, 15, '2025-03-03', 'present'), (16, 16, '2025-03-03', 'absent'),
    (17, 17, '2025-03-03', 'present'), (18, 18, '2025-03-03', 'late'),
    (19, 19, '2025-03-03', 'present'), (20, 20, '2025-03-03', 'remote'),
    (21, 21, '2025-03-03', 'present'), (22, 22, '2025-03-03', 'present'),
    (23, 23, '2025-03-03', 'late'), (24, 24, '2025-03-03', 'present'),
    (25, 25, '2025-03-03', 'remote'), (26, 26, '2025-03-03', 'present'),
    (27, 27, '2025-03-03', 'present'), (28, 28, '2025-03-03', 'absent'),
    (29, 29, '2025-03-03', 'present'), (30, 30, '2025-03-03', 'present'),
    (31, 31, '2025-03-03', 'late'), (32, 32, '2025-03-03', 'present'),
    (33, 33, '2025-03-03', 'remote'), (34, 34, '2025-03-03', 'present'),
    (35, 35, '2025-03-03', 'present'), (36, 36, '2025-03-03', 'present'),
    (37, 1, '2025-03-04', 'present'), (38, 2, '2025-03-04', 'present'),
    (39, 3, '2025-03-04', 'remote'), (40, 4, '2025-03-04', 'present'),
    (41, 5, '2025-03-04', 'late'), (42, 6, '2025-03-04', 'present'),
    (43, 19, '2025-03-04', 'present'), (44, 20, '2025-03-04', 'present'),
    (45, 25, '2025-03-04', 'absent'), (46, 30, '2025-03-04', 'present')
ON DUPLICATE KEY UPDATE status = VALUES(status);

INSERT INTO leaves (leave_id, employee_id, leave_type, start_date, end_date, leave_status) VALUES
    (1, 3, 'annual', '2025-04-14', '2025-04-18', 'approved'),
    (2, 6, 'sick', '2025-03-03', '2025-03-04', 'approved'),
    (3, 10, 'personal', '2025-05-02', '2025-05-02', 'pending'),
    (4, 15, 'annual', '2025-06-09', '2025-06-13', 'approved'),
    (5, 18, 'sick', '2025-02-10', '2025-02-11', 'approved'),
    (6, 22, 'unpaid', '2025-07-21', '2025-07-25', 'pending'),
    (7, 27, 'annual', '2025-08-04', '2025-08-08', 'approved'),
    (8, 28, 'personal', '2025-03-17', '2025-03-17', 'rejected'),
    (9, 31, 'annual', '2025-09-15', '2025-09-19', 'pending'),
    (10, 35, 'sick', '2025-01-27', '2025-01-27', 'approved'),
    (11, 1, 'parental', '2025-10-01', '2025-10-31', 'approved'),
    (12, 24, 'annual', '2025-11-10', '2025-11-14', 'cancelled')
ON DUPLICATE KEY UPDATE
    employee_id = VALUES(employee_id), leave_type = VALUES(leave_type),
    start_date = VALUES(start_date), end_date = VALUES(end_date), leave_status = VALUES(leave_status);
