"""Integrity checks for the tracked synthetic company database SQL assets."""

from pathlib import Path
import re

from config.settings import Settings
from database.sql_validator import validate_readonly_sql

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def test_company_sample_schema_has_all_tables_keys_and_indexes() -> None:
    schema = (SAMPLES / "company_db_schema.sql").read_text(encoding="utf-8")
    assert "CREATE DATABASE IF NOT EXISTS company_db" in schema
    for table in ("employees", "departments", "projects", "attendance", "leaves"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
    assert schema.count("PRIMARY KEY") == 5
    assert schema.count("FOREIGN KEY") == 4
    assert "UNIQUE KEY uq_attendance_employee_date" in schema
    assert schema.count("KEY idx_") >= 10


def test_company_sample_seed_has_36_employees_and_related_records() -> None:
    seed = (SAMPLES / "company_db_seed.sql").read_text(encoding="utf-8")
    employee_block = seed.split("INSERT INTO employees", 1)[1].split("ON DUPLICATE KEY UPDATE", 1)[0]
    employee_ids = re.findall(r"^\s*\((\d+),\s*'[^']+',\s*\d+,\s*[\d.]+,", employee_block, re.MULTILINE)
    assert len(employee_ids) == 36
    assert len(set(employee_ids)) == 36
    assert "INSERT INTO departments" in seed
    assert "INSERT INTO projects" in seed
    assert "INSERT INTO attendance" in seed
    assert "INSERT INTO leaves" in seed


def test_company_readonly_user_is_scoped_to_company_db() -> None:
    user_sql = (SAMPLES / "company_db_readonly_user.sql").read_text(encoding="utf-8")
    assert "GRANT SELECT, SHOW VIEW ON company_db.*" in user_sql
    assert "INSERT" not in user_sql.upper()
    assert "UPDATE" not in user_sql.upper()
    assert "DELETE" not in user_sql.upper()


def test_sample_query_file_contains_only_validated_select_statements() -> None:
    source = (SAMPLES / "company_db_sample_queries.sql").read_text(encoding="utf-8")
    statements = []
    for part in source.split(";"):
        sql = "\n".join(line for line in part.splitlines() if not line.lstrip().startswith("--")).strip()
        if sql.upper().startswith("SELECT"):
            statements.append(sql)
            validate_readonly_sql(sql)
    assert len(statements) == 10


def test_querymate_default_schema_is_company_db() -> None:
    assert Settings().mysql_database == "company_db"
