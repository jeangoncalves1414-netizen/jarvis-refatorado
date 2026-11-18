from __future__ import annotations

import json
from typing import Any, Callable

from app.agent.action_gateway import run_action

MAX_WATER_ADD_ML = 5000


def _water_amount(value: Any) -> int | None:
    if value is None:
        return 250
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        amount = float(value)
    except ValueError:
        return None
    if not 1 <= amount <= MAX_WATER_ADD_ML:
        return None
    return int(round(amount))


def handle_evolute_routes(
    path: str,
    body: bytes,
    send_json: Callable[[int, dict[str, Any]], None],
    friendly_error: Callable[[BaseException, str], str],
) -> bool:
    if path == "/api/evolute/water/add":
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            if not isinstance(payload, dict):
                raise ValueError("payload")
            amount_ml = _water_amount(payload.get("amount_ml"))
            if amount_ml is None:
                send_json(400, {"ok": False, "error": f"Quantidade de água inválida: informe de 1 a {MAX_WATER_ADD_ML} ml."})
                return True
            outcome = run_action(
                "lifeos_tool", {"action": "add_water", "amount": amount_ml},
                source="api:water", user_text=f"Registrar {amount_ml} ml de água", origin="window",
            )
            action = outcome.action.public_dict() if outcome.action else None
            if outcome.pending:
                send_json(202, {"ok": False, "pending": True, "error": "O registro de água aguarda aprovação na Central.", "action": action})
                return True
            result = outcome.result.data.get("data") if outcome.succeeded and outcome.result else None
            if not isinstance(result, dict):
                send_json(500, {"ok": False, "error": "Não foi possível registrar a água.", "action": action})
                return True
            try:
                from app.agent.popups import build_popup
                result["popup"] = build_popup(
                    "water", {}, origin="command",
                    animate={"from_ml": max(0, int(result["total_ml"]) - int(result["added_ml"])), "to_ml": int(result["total_ml"])},
                )
            except Exception:
                pass
            result["action"] = action
            send_json(200, result)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            send_json(400, {"ok": False, "error": "Pedido de água inválido."})
        except Exception as exc:
            send_json(500, {"ok": False, "error": friendly_error(exc, "registrar a água")})
        return True

    if path == "/api/evolute/habit/toggle":
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            habit_ref = str(payload.get("habit_name_or_id") or "")
            completed = payload.get("completed", True)
            from app.services.lifeos import LifeOSService
            send_json(200, LifeOSService.toggle_habit(habit_ref, completed=completed))
        except Exception as exc:
            send_json(500, {"ok": False, "error": friendly_error(exc, "atualizar o hábito")})
        return True

    if path == "/api/evolute/habit/priority":
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            habit_ref = str(payload.get("habit_name_or_id") or "")
            from app.services.lifeos import LifeOSService
            send_json(200, LifeOSService.toggle_habit_priority(habit_ref))
        except Exception as exc:
            send_json(500, {"ok": False, "error": friendly_error(exc, "atualizar a prioridade do hábito")})
        return True

    return False
