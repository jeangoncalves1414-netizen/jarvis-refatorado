from datetime import date

import pytest

from app.services import finance, habits
from app.services.lifeos import LifeOSService
from scripts.sync_mobile_routine import apply_change, snapshot


def test_mobile_edits_replay_and_conflict(tmp_path, monkeypatch):
    monkeypatch.setattr(habits, "DB_PATH", tmp_path / "routine.db")
    monkeypatch.setattr(LifeOSService, "get_data_bucket", lambda: {})
    habits.init_db()
    finance.init_finance_tables()
    day = date.today().isoformat()
    expense = dict(name="Café", type="expense", amount=12.5)
    changes = [
        dict(kind="habit", id="h", before=None, after="Ler", date=""),
        dict(kind="check", id="h", before=False, after=True, date=day),
        dict(kind="finance", id="f", before=None, after=expense, date=day),
    ]
    for _ in range(2):
        for change in changes:
            apply_change(change)
    apply_change(dict(kind="habit", id="h", before="Ler", after="Ler dez páginas", date=""))
    apply_change(dict(kind="finance", id="f", before=expense, after=dict(expense, amount=15), date=day))
    data = snapshot(4)
    assert [(h["name"], h["done"]) for h in data["habits"]] == [("Ler dez páginas", day)]
    assert [f["amount"] for f in data["finance"]] == [15]
    with pytest.raises(ValueError, match="mudou no PC"):
        apply_change(dict(kind="habit", id="h", before="Ler", after="Caminhar", date=""))


def test_finance_summary_and_retried_undo(tmp_path, monkeypatch):
    monkeypatch.setattr(habits, "DB_PATH", tmp_path / "routine.db")
    monkeypatch.setattr(finance.sync_tombstones, "TOMBSTONES_FILE", tmp_path / "deleted.json")
    finance.init_finance_tables()
    day = date.today().isoformat()
    with habits.get_db_connection() as conn:
        conn.executemany("INSERT INTO finance_transactions VALUES (?, 'expense', .37, 'Outros', 'Teste', ?, ?)",
                         [(str(i), day, i) for i in range(105)])
    recent, older = finance.FinanceService.mobile_snapshot()
    assert len(recent) == 100
    assert older == [{"date": day, "type": "expense", "cents": 185}]
    expense = dict(name="Café", type="expense", amount=12.5)
    change = dict(kind="finance", id="mobile-test", before=None, after=expense, date=day)
    undo = dict(change, before=expense, after=None)
    apply_change(undo)
    apply_change(change)
    finance.FinanceService.update_transaction("mobile-test", "expense", 12.5, "Cafés", "Café", day)
    with pytest.raises(ValueError, match="mudou no PC"):
        apply_change(undo)
    finance.FinanceService.update_transaction("mobile-test", "expense", 12.5, "Outros", "Café", day)
    apply_change(undo)
    apply_change(undo)
    assert finance.FinanceService.get_transaction("mobile-test") is None
