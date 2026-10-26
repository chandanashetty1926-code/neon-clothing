import os
import mysql.connector

DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
    "ssl_disabled": False,
    "connection_timeout": 15,
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)
