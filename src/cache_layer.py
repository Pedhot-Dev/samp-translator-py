
import sqlite3
import hashlib
import os

class CacheLayer:
    def __init__(self, db_path="rp_translator.db"):
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database and create tables if they don't exist."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            c = self.conn.cursor()
            
            # Cache table
            c.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                hash TEXT PRIMARY KEY,
                result TEXT
            )
            """)
            
            # Logs table for debugging/history
            c.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                time TEXT DEFAULT CURRENT_TIMESTAMP,
                original TEXT,
                result TEXT,
                style TEXT
            )
            """)
            
            self.conn.commit()
        except Exception as e:
            print(f"Error initializing database: {e}")

    def _hash_text(self, text, style):
        """Create a unique hash for the text and style combination."""
        key = f"{style}::{text}"
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, text, style):
        """Retrieve a translation from the cache."""
        if not self.conn:
            return None
            
        try:
            h = self._hash_text(text, style)
            c = self.conn.cursor()
            c.execute("SELECT result FROM cache WHERE hash=?", (h,))
            row = c.fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None

    def set(self, text, style, result):
        """Save a translation to the cache."""
        if not self.conn:
            return
            
        try:
            h = self._hash_text(text, style)
            c = self.conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO cache (hash, result) VALUES (?,?)",
                (h, result)
            )
            self.conn.commit()
        except Exception as e:
            print(f"Cache set error: {e}")

    def log(self, original, result, style):
        """Log the translation event."""
        if not self.conn:
            return
            
        try:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO logs (original, result, style) VALUES (?,?,?)",
                (original, result, style)
            )
            self.conn.commit()
        except Exception as e:
            print(f"Logging error: {e}")

    def close(self):
        if self.conn:
            self.conn.close()
