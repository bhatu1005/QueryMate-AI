-- Example SELECT-only questions for QueryMate's company_db dataset.
USE company_db;

-- 1. List employees with their department.
SELECT e.employee_id, e.employee_name, d.department_name, e.designation
FROM employees AS e
JOIN departments AS d ON d.department_id = e.department_id
ORDER BY d.department_name, e.employee_name;

-- 2. Average salary and employee count by department.
SELECT d.department_name, COUNT(*) AS employee_count, ROUND(AVG(e.salary), 2) AS average_salary
FROM employees AS e
JOIN departments AS d ON d.department_id = e.department_id
GROUP BY d.department_id, d.department_name
ORDER BY average_salary DESC;

-- 3. Employees earning more than 90,000.
SELECT employee_name, designation, salary
FROM employees
WHERE salary > 90000
ORDER BY salary DESC;

-- 4. Active projects by department.
SELECT d.department_name, p.project_name, p.start_date, p.status
FROM projects AS p
JOIN departments AS d ON d.department_id = p.department_id
WHERE p.status = 'active'
ORDER BY d.department_name, p.start_date;

-- 5. Attendance status counts by day.
SELECT attendance_date, status, COUNT(*) AS employee_count
FROM attendance
GROUP BY attendance_date, status
ORDER BY attendance_date, status;

-- 6. Attendance records for one employee.
SELECT e.employee_name, a.attendance_date, a.status
FROM attendance AS a
JOIN employees AS e ON e.employee_id = a.employee_id
WHERE e.employee_id = 6
ORDER BY a.attendance_date;

-- 7. Approved leave with employee and department.
SELECT e.employee_name, d.department_name, l.leave_type, l.start_date, l.end_date, l.leave_status
FROM leaves AS l
JOIN employees AS e ON e.employee_id = l.employee_id
JOIN departments AS d ON d.department_id = e.department_id
WHERE l.leave_status = 'approved'
ORDER BY l.start_date;

-- 8. Pending leave requests.
SELECT e.employee_name, l.leave_type, l.start_date, l.end_date
FROM leaves AS l
JOIN employees AS e ON e.employee_id = l.employee_id
WHERE l.leave_status = 'pending'
ORDER BY l.start_date;

-- 9. Project counts by status.
SELECT status, COUNT(*) AS project_count
FROM projects
GROUP BY status
ORDER BY project_count DESC;

-- 10. Longest-tenured employees.
SELECT employee_name, designation, joining_date
FROM employees
ORDER BY joining_date
LIMIT 10;
