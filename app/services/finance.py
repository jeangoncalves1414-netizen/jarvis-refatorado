"""Personal Finance Management Service (inspired by Firefly III & Actual Budget).

Tracks income and expense transactions, category budgets, and current net balance.
Stores data in persistent SQLite database (data/lifestyle.db).
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any

from app.services.habits import get_db_connection


def init_finance_tables() -> None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_transactions (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,          -- 'expense' or 'income'
                amount REAL NOT NULL,
                category TEXT DEFAULT 'Outros',
                description TEXT DEFAULT '',
                date_str TEXT NOT NULL,      -- YYYY-MM-DD
                timestamp REAL NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_categories (
                name TEXT PRIMARY KEY,
                monthly_limit REAL DEFAULT 0.0
            )
        """)
        conn.commit()


init_finance_tables()


class FinanceService:
    """Service to handle personal finances, expenses, and budgets."""

    @staticmethod
    def add_transaction(
        trans_id: str,
        type_: str,
        amount: float,
        category: str = "Outros",
        description: str = "",
        date_str: str = "",
    ) -> dict[str, Any]:
        if not date_str:
            date_str = date.today().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute(
                """
                INSERT OR REPLACE INTO finance_transactions (id, type, amount, category, description, date_str, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (trans_id, type_.lower(), float(amount), category, description, date_str, now),
            )
            conn.commit()
        return FinanceService.get_summary()

    @staticmethod
    def list_transactions(limit: int = 50) -> list[dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM finance_transactions ORDER BY date_str DESC, timestamp DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def delete_transaction(trans_id: str) -> dict[str, Any]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM finance_transactions WHERE id = ?", (trans_id,))
            conn.commit()
        return FinanceService.get_summary()

    @staticmethod
    def get_summary(month_str: str = "") -> dict[str, Any]:
        if not month_str:
            month_str = date.today().strftime("%Y-%m")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT type, SUM(amount) as total FROM finance_transactions WHERE date_str LIKE ? GROUP BY type",
                (f"{month_str}%",),
            )
            rows = cursor.fetchall()
            income = 0.0
            expense = 0.0
            for r in rows:
                if r["type"] == "income":
                    income = float(r["total"] or 0.0)
                elif r["type"] == "expense":
                    expense = float(r["total"] or 0.0)

            # Calculate total historical balance
            cursor.execute(
                "SELECT SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as net_balance FROM finance_transactions"
            )
            net_row = cursor.fetchone()
            total_balance = float((net_row and net_row["net_balance"]) or 0.0)

            # Category breakdown for current month
            cursor.execute(
                "SELECT category, SUM(amount) as total FROM finance_transactions WHERE date_str LIKE ? AND type = 'expense' GROUP BY category ORDER BY total DESC",
                (f"{month_str}%",),
            )
            categories = [dict(c) for c in cursor.fetchall()]

            return {
                "month": month_str,
                "income": round(income, 2),
                "expense": round(expense, 2),
                "month_net": round(income - expense, 2),
                "total_balance": round(total_balance, 2),
                "categories": categories,
            }
