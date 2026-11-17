"""Troca os dados da rotina com o APK de desenvolvimento no Android autorizado por USB."""
import json
import subprocess
from datetime import date, datetime
from pathlib import Path

from app.services.finance import FinanceService
from app.services.personal_habits import PersonalHabits

PACKAGE = "com.example.jarvismobile"
URI = "content://" + PACKAGE + ".routine"


def transfer(action):
    result = subprocess.check_output(["adb", "-d", "shell", "content", "call", "--uri", URI,
                                      "--method", action], text=True)
    if "ok=true" not in result:
        raise RuntimeError("Transferência interrompida. Feche a edição no celular e sincronize novamente.")


def finance_fields(row):
    if row is not None:
        return {"type": row["type"], "name": row["description"], "amount": row["amount"]}


class SyncConflict(ValueError):
    def __init__(self, key, current):
        super().__init__(f"O registro {key} mudou no PC. A alteração do celular foi preservada.")
        self.current = current


def apply_change(change):
    kind, key = change["kind"], change["id"]
    before, after = change["before"], change["after"]
    if kind == "finance":
        row = FinanceService.get_transaction(key)
        current = finance_fields(row)
    elif kind == "habit":
        row = PersonalHabits.get_habit(key)
        current = row["name"] if row else None
    elif kind == "check":
        rows = PersonalHabits.list_habits(day=change["date"])
        row = next((r for r in rows if r["id"] == key), None)
        if not row:
            raise ValueError("Hábito removido no PC. A marcação continua no celular.")
        current = bool(row["completed_today"])
    else:
        raise ValueError("Operação desconhecida.")
    if current == after:
        return
    if current != before:
        raise SyncConflict(key, current)
    if kind == "habit":
        if not isinstance(after, str) or not 0 < len(after.strip()) <= 120:
            raise ValueError("Nome de hábito inválido.")
        if row:
            PersonalHabits.update_habit(key, name=after)
        else:
            PersonalHabits.create_habit(key, after)
    elif kind == "check":
        fn = PersonalHabits.check_in if after else PersonalHabits.uncheck_in
        fn(key, change["date"])
    else:
        if after is None:
            if not key.startswith("mobile-") or not isinstance(before, dict):
                raise ValueError("Somente lançamentos criados no celular podem ser desfeitos.")
            expected = {
                "description": before["name"], "amount": before["amount"], "type": before["type"],
                "date_str": change["date"], "category": "Outros",
            }
            try:
                FinanceService.delete_transaction(key, expected=expected)
            except ValueError as exc:
                raise SyncConflict(key, finance_fields(FinanceService.get_transaction(key))) from exc
            return
        entry = FinanceService.normalize_entry(after["type"], after["amount"], (row or {}).get("category"),
                                              after["name"], (row or {}).get("date_str") or change["date"])
        fn = FinanceService.update_transaction if row else FinanceService.add_transaction
        fn(key, entry["type"], entry["amount"], entry["category"], entry["description"], entry["date_str"])


def snapshot(revision):
    today = date.today().isoformat()
    habits = [{"id": h["id"], "name": h["name"], "days": h["days_of_week"],
               "block": h.get("routine_block"), "time": h.get("start_time") or "",
               "times": h.get("time_exceptions") or {}, "priority": bool(h.get("isPriority")),
               "start": h.get("created_date") or "", "done": today if h["completed_today"] else ""}
              for h in PersonalHabits.list_habits()]
    recent, older_totals = FinanceService.mobile_snapshot()
    finance = [dict(finance_fields(f), id=f["id"], date=f["date_str"])
               for f in recent]
    return dict(rev=revision, habits=habits, finance=finance, olderFinance=older_totals, queue=[],
                synced=datetime.now().strftime("%d/%m/%Y %H:%M"))


def main():
    if Path.cwd().resolve() != Path(__file__).resolve().parents[1]:
        raise SystemExit("Execute na pasta do projeto Jarvis.")
    transfer("export")
    device = json.loads(subprocess.check_output(
        ["adb", "-d", "exec-out", "run-as", PACKAGE, "cat", "files/routine-out.json"]))
    for change in device["queue"]:
        apply_change(change)
    result = snapshot(device["rev"])
    subprocess.run(["adb", "-d", "exec-in", "run-as", PACKAGE, "tee", "files/routine-in.json"],
                   input=json.dumps(result).encode(), stdout=subprocess.DEVNULL, check=True)
    transfer("import")
    print(f"Sincronizado. {len(result['habits'])} hábitos e {len(result['finance'])} lançamentos no celular.")


if __name__ == "__main__":
    main()

