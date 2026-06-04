from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import DB_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class IntelligenceDB:
    """Single SQLite gateway used by the CLI, UI, orchestrator, and RAG."""

    def __init__(self, path=DB_PATH):
        self.path = path
        self.init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # Compatibility with the original main.py.
    def _connect(self) -> sqlite3.Connection:
        return self.connect()

    def init(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    nse_symbol TEXT,
                    bse_symbol TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS intelligence_packets (
                    company_id INTEGER PRIMARY KEY,
                    packet_json TEXT,
                    updated_at TEXT,
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    data JSON
                )
                """
            )
            self._ensure_column(conn, "companies", "nse_symbol", "TEXT")
            self._ensure_column(conn, "companies", "bse_symbol", "TEXT")
            self._ensure_column(conn, "companies", "created_at", "TEXT")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def add_company(self, name: str, nse_symbol: str | None = None) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("company name cannot be empty")
        clean_symbol = nse_symbol.strip().upper().replace(".NS", "") if nse_symbol else None
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO companies (name, nse_symbol, created_at)
                VALUES (?, ?, ?)
                """,
                (clean_name, clean_symbol, utc_now()),
            )
            if clean_symbol:
                conn.execute(
                    "UPDATE companies SET nse_symbol=? WHERE name=?",
                    (clean_symbol, clean_name),
                )
            row = conn.execute("SELECT id FROM companies WHERE name=?", (clean_name,)).fetchone()
            conn.commit()
            return int(row["id"])

    def remove_company(self, name: str) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM companies WHERE name=?", (name,)).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM intelligence_packets WHERE company_id=?", (row["id"],))
            conn.execute("DELETE FROM companies WHERE id=?", (row["id"],))
            conn.commit()
            return True

    def list_companies(self) -> list[str]:
        with self.connect() as conn:
            return [row["name"] for row in conn.execute("SELECT name FROM companies ORDER BY name")]

    def list_company_rows(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM companies ORDER BY name")]

    def get_company_id(self, name: str) -> int | None:
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM companies WHERE name=?", (name,)).fetchone()
            return int(row["id"]) if row else None

    def get_company_name(self, company_id: int) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT name FROM companies WHERE id=?", (company_id,)).fetchone()
            return row["name"] if row else None

    def get_nse_symbol(self, name: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT nse_symbol FROM companies WHERE name=?", (name,)).fetchone()
            return row["nse_symbol"] if row and row["nse_symbol"] else None

    def set_nse_symbol(self, name: str, symbol: str) -> None:
        clean = symbol.strip().upper().replace(".NS", "")
        with self.connect() as conn:
            conn.execute("UPDATE companies SET nse_symbol=? WHERE name=?", (clean, name))
            conn.commit()

    def save_packet(self, company_id: int, packet: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO intelligence_packets
                (company_id, packet_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (company_id, json.dumps(packet, default=str), utc_now()),
            )
            conn.commit()

    def get_packet(self, company_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT packet_json FROM intelligence_packets WHERE company_id=?",
                (company_id,),
            ).fetchone()
        if not row or not row["packet_json"]:
            return None
        return json.loads(row["packet_json"])

    def get_all_packets(self) -> dict[str, dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.name, p.packet_json
                FROM intelligence_packets p
                JOIN companies c ON c.id = p.company_id
                ORDER BY c.name
                """
            ).fetchall()
        return {row["name"]: json.loads(row["packet_json"]) for row in rows if row["packet_json"]}

    def log_message(self, role: str, message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO messages (ts, role, message) VALUES (?, ?, ?)",
                (utc_now(), role, message),
            )
            conn.commit()

    def recent_messages(self, limit: int = 8) -> list[dict[str, str]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT role, message FROM messages ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

