import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "connection_timeout": 10,
    "ssl_disabled": False,
}

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="chatpool",
            pool_size=3,
            pool_reset_session=False,
            **DB_CONFIG,
        )
    return _pool


def query(sql: str, params=None, fetch=False):
    conn = get_pool().get_connection()
    try:
        # Reconecta si MySQL cerró la conexión por inactividad
        conn.ping(reconnect=True, attempts=3, delay=1)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params or ())
            result = cur.fetchall() if fetch else None
            conn.commit()
            return result
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass