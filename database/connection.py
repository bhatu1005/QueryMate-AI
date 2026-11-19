"""MySQL connection factory using environment settings and read-only credentials."""

import mysql.connector
from mysql.connector.connection import MySQLConnection

from config.settings import Settings, get_settings


def connect_readonly(settings: Settings | None = None) -> MySQLConnection:
    """Open a short-lived MySQL connection with credentials held in configuration."""
    active = settings or get_settings()
    return mysql.connector.connect(
        host=active.mysql_host,
        port=active.mysql_port,
        database=active.mysql_database,
        user=active.mysql_user,
        password=active.mysql_password.get_secret_value(),
        connection_timeout=active.mysql_connect_timeout,
        autocommit=False,
    )
