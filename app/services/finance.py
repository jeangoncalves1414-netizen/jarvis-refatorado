"""Personal Finance Management Service (inspired by Firefly III & Actual Budget).

Tracks income and expense transactions, category budgets, and current net balance.
Stores data in persistent SQLite database (data/lifestyle.db).
"""
from __future__ import annotations

import math
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

ENTRY_TYPES = frozenset({"expense", "income"})
MAX_AMOUNT = 1_000_000_000.0
MAX_CATEGORY = 60
MAX_DESCRIPTION = 300


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
    def normalize_entry(
        type_: Any,
        amount: Any,
        category: Any = "",
        description: Any = "",
        date_str: Any = "",
    ) -> dict[str, Any]:
        """Valida e normaliza um lançamento manual. Levanta ValueError com mensagem em pt-BR."""
        kind = str(type_ or "").strip().lower()
        if kind not in ENTRY_TYPES:
            raise ValueError("Tipo inválido: use 'expense' (despesa) ou 'income' (receita).")
        try:
            value = float(amount)
        except (TypeError, ValueError):
            raise ValueError("Informe um valor numérico.") from None
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Informe um valor maior que zero.")
        if value > MAX_AMOUNT:
            raise ValueError("Valor acima do limite permitido.")
        text_category = str(category or "").strip()[:MAX_CATEGORY] or "Outros"
        text_description = str(description or "").strip()[:MAX_DESCRIPTION]
        day = str(date_str or "").strip() or date.today().isoformat()
        try:
            day = date.fromisoformat(day).isoformat()
        except ValueError:
            raise ValueError("Data inválida: use o formato AAAA-MM-DD.") from None
        return {"type": kind, "amount": round(value, 2), "category": text_category, "description": text_description, "date_str": day}

    @staticmethod
    def get_transaction(trans_id: str) -> dict[str, Any] | None:
        with get_db_connection() as conn:
            row = conn.cursor().execute("SELECT * FROM finance_transactions WHERE id = ?", (trans_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def _filter_clause(date_from: str = "", date_to: str = "", type_: str = "", category: str = "") -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if date_from:
            clauses.append("date_str >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("date_str <= ?")
            params.append(date_to)
        if type_:
            clauses.append("type = ?")
            params.append(type_.lower())
        if category:
            clauses.append("category = ?")
            params.append(category)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    @staticmethod
    def query_transactions(
        date_from: str = "", date_to: str = "", type_: str = "", category: str = "", limit: int = 200
    ) -> dict[str, Any]:
        """Lista lançamentos filtrados e calcula os totais do mesmo filtro no servidor."""
        where, params = FinanceService._filter_clause(date_from, date_to, type_, category)
        limit = max(1, min(int(limit), 1000))
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM finance_transactions{where} ORDER BY date_str DESC, timestamp DESC LIMIT ?",
                [*params, limit],
            )
            transactions = [dict(r) for r in cursor.fetchall()]
            cursor.execute(
                f"SELECT type, COUNT(*) AS n, SUM(amount) AS total FROM finance_transactions{where} GROUP BY type", params
            )
            income = expense = 0.0
            count = 0
            for r in cursor.fetchall():
                count += int(r["n"] or 0)
                if r["type"] == "income":
                    income = float(r["total"] or 0.0)
                elif r["type"] == "expense":
                    expense = float(r["total"] or 0.0)
            cursor.execute(
                f"SELECT category, type, SUM(amount) AS total FROM finance_transactions{where} GROUP BY category, type ORDER BY total DESC",
                params,
            )
            by_category = [{"category": r["category"], "type": r["type"], "total": round(float(r["total"] or 0.0), 2)} for r in cursor.fetchall()]
            cursor.execute("SELECT DISTINCT category FROM finance_transactions ORDER BY category COLLATE NOCASE")
            categories = [r["category"] for r in cursor.fetchall() if r["category"]]
        return {
            "transactions": transactions,
            "totals": {
                "income": round(income, 2),
                "expense": round(expense, 2),
                "net": round(income - expense, 2),
                "count": count,
                "by_category": by_category,
            },
            "categories": categories,
            "truncated": count > len(transactions),
        }

    @staticmethod
    def update_transaction(
        trans_id: str,
        type_: Any,
        amount: Any,
        category: Any = "",
        description: Any = "",
        date_str: Any = "",
    ) -> dict[str, Any] | None:
        """Edita um lançamento existente (valida os campos). Retorna None se o id não existir."""
        entry = FinanceService.normalize_entry(type_, amount, category, description, date_str)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE finance_transactions SET type = ?, amount = ?, category = ?, description = ?, date_str = ?, timestamp = ? WHERE id = ?",
                (entry["type"], entry["amount"], entry["category"], entry["description"], entry["date_str"], time.time(), trans_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return FinanceService.get_transaction(trans_id)

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
