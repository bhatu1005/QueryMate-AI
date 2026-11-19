-- Run as a MySQL administrator after company_db_schema.sql.
-- Replace the password placeholder before execution; do not commit the replacement.
CREATE USER IF NOT EXISTS 'querymate_readonly'@'localhost'
    IDENTIFIED BY 'REPLACE_WITH_A_STRONG_LOCAL_PASSWORD';
ALTER USER 'querymate_readonly'@'localhost'
    IDENTIFIED BY 'REPLACE_WITH_A_STRONG_LOCAL_PASSWORD';
GRANT SELECT, SHOW VIEW ON company_db.* TO 'querymate_readonly'@'localhost';
FLUSH PRIVILEGES;

-- Confirm the account has no write privileges:
SHOW GRANTS FOR 'querymate_readonly'@'localhost';
