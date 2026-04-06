import sqlite3
import os
import logging
from config import Config

logger = logging.getLogger(__name__)

_db_path = None


def _get_db_path():
    global _db_path
    if _db_path is None:
        _db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            Config.DATABASE_PATH,
        )
    return _db_path


def get_connection():
    """Returns a new SQLite connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(_get_db_path(), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'sales'
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kodikos TEXT UNIQUE NOT NULL,
            factory_code TEXT,
            description TEXT,
            category TEXT DEFAULT 'Unknown',
            subcategory TEXT DEFAULT 'Unknown',
            stock REAL DEFAULT 0,
            available_stock REAL DEFAULT 0,
            embedding BLOB
        );

        CREATE TABLE IF NOT EXISTS query_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT UNIQUE NOT NULL,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            query TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_products_kodikos ON products (kodikos);
        CREATE INDEX IF NOT EXISTS idx_products_embedding ON products (id) WHERE embedding IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_query_cache_query ON query_cache (query);
        CREATE INDEX IF NOT EXISTS idx_search_logs_user ON search_logs (user);
        CREATE INDEX IF NOT EXISTS idx_search_logs_date ON search_logs (created_at);
    """)

    try:
        cursor.execute("ALTER TABLE products ADD COLUMN available_stock REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create default admin user with hashed password
    from werkzeug.security import generate_password_hash

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        hashed = generate_password_hash("admin123")
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", hashed, "admin"),
        )
        logger.info("Default admin user created (username: admin, password: admin123)")

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")
