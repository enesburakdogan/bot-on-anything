# encoding:utf-8

import os
import sqlite3
import threading
import time


class Storage:
    """SQLite store remembering which listings were seen and applied to,
    so restarts never cause duplicate applications."""

    def __init__(self, db_path):
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS listings ("
            " uid TEXT PRIMARY KEY,"
            " site TEXT NOT NULL,"
            " url TEXT,"
            " title TEXT,"
            " price INTEGER,"
            " first_seen INTEGER NOT NULL,"
            " applied_at INTEGER,"
            " apply_status TEXT"
            ")"
        )
        self._conn.commit()

    def is_seen(self, uid):
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM listings WHERE uid=?", (uid,)).fetchone()
        return row is not None

    def mark_seen(self, listing):
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO listings (uid, site, url, title, price, first_seen)"
                " VALUES (?,?,?,?,?,?)",
                (listing.uid, listing.site, listing.url, listing.title, listing.price, int(time.time())),
            )
            self._conn.commit()

    def mark_applied(self, uid, status):
        with self._lock:
            self._conn.execute(
                "UPDATE listings SET applied_at=?, apply_status=? WHERE uid=?",
                (int(time.time()), status, uid),
            )
            self._conn.commit()

    def applications_since(self, seconds):
        """Number of successful applications within the last `seconds`."""
        cutoff = int(time.time()) - seconds
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM listings WHERE apply_status='sent' AND applied_at>=?",
                (cutoff,),
            ).fetchone()
        return row[0]

    def close(self):
        with self._lock:
            self._conn.close()
