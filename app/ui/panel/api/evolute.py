from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
import urllib.request
import urllib.error

# Local preferencial do banco do Evolute (mantém compatibilidade total)
_DOCUMENTS_DB = Path(os.path.expanduser("~")) / "Documents" / "Evolute" / "data" / "lifeos_db.json"
_LOCAL_DB = Path(__file__).resolve().parents[4] / "data" / "lifeos_db.json"
from app.services.lifeos import _DB_LOCK as _SYNC_LOCK

def _get_db_file() -> Path:
    if _DOCUMENTS_DB.parent.exists():
        _DOCUMENTS_DB.parent.mkdir(parents=True, exist_ok=True)
        return _DOCUMENTS_DB
    _LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
    return _LOCAL_DB


def handle_evolute_sync_get() -> tuple[int, dict[str, Any]]:
    """Retorna o estado do banco do Life OS."""
    db_file = _get_db_file()
    try:
        if not db_file.exists():
            return 200, {"data": None, "updatedAt": 0}
        content = db_file.read_text(encoding="utf-8")
        parsed = json.loads(content)
        return 200, parsed
    except Exception as err:
        return 500, {"error": f"Falha ao ler dados de sincronização: {err}"}


def handle_evolute_sync_post(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Persiste uma revisão do Life OS sem sobrescrever uma revisão mais nova."""
    data = body.get("data")
    if not isinstance(data, dict) or not data:
        return 400, {"error": "Payload data ausente."}

    db_file = _get_db_file()
    try:
        client_updated_at = int(body.get("updatedAt") or 0)
        base_updated_at = int(body.get("baseUpdatedAt") or 0)
    except (TypeError, ValueError):
        return 400, {"error": "updatedAt inválido."}

    try:
        with _SYNC_LOCK:
            current: dict[str, Any] = {}
            if db_file.exists():
                current = json.loads(db_file.read_text(encoding="utf-8"))
            current_updated_at = int(current.get("updatedAt") or 0)
            if base_updated_at and current_updated_at > base_updated_at:
                return 409, {
                    "error": "Há uma alteração mais recente em outro dispositivo.",
                    "conflict": True,
                    "data": current.get("data"),
                    "updatedAt": current_updated_at,
                }

            updated_at = max(client_updated_at, int(time.time() * 1000), current_updated_at + 1)
            current_data = current.get('data') or {}
            if 'lifeos_workout_sessions' in current_data:
                # Sessions are edited through the organizer. Older exercise-only
                # clients must not drop the session or its derived exercise rows.
                data = dict(data)
                data['lifeos_workout_sessions'] = current_data['lifeos_workout_sessions']
                incoming = data.get('lifeos_workouts', current_data.get('lifeos_workouts', []))
                data['lifeos_workouts'] = [r for r in incoming if not r.get('jarvis_session_id')] + [r for r in current_data.get('lifeos_workouts', []) if r.get('jarvis_session_id')]
            payload = {"data": data, "updatedAt": updated_at}
            db_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = db_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(db_file)
        return 200, {"success": True, "updatedAt": updated_at}
    except Exception as err:
        return 500, {"error": f"Falha ao persistir dados: {err}"}


def handle_evolute_ai_chat(body: dict[str, Any], orchestrator: Any = None) -> tuple[int, dict[str, Any]]:
    """
    Processa prompts de IA do Life OS (mentoria estóica, resumos Feynman, etc.).
    Tenta chaves Oxxy fornecidas ou usa o serviço de LLM nativo do Jarvis.
    """
    prompt = body.get("prompt")
    if not prompt:
        return 400, {"error": "Prompt is required."}

    sys_prompt = body.get("systemPrompt") or (
        "Você é o Mentor Estóico do Life OS. Seja radicalmente honesto, direto, "
        "minimalista e focado em disciplina, foco e superação. Não use desculpas."
    )

    keys = body.get("keys", [])
    base_url = (body.get("baseUrl") or "https://api.openai.com/v1").rstrip("/")
    model = body.get("model") or "gpt-4o-mini"

    # 1. Tentativa via chaves Oxxy / OpenAI compatíveis enviadas pelo Life OS
    if isinstance(keys, list) and len(keys) > 0:
        for i, key in enumerate(keys):
            curr_key = (key or "").strip()
            if not curr_key:
                continue
            try:
                req_data = json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.4
                }).encode("utf-8")

                req = urllib.request.Request(
                    f"{base_url}/chat/completions",
                    data=req_data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {curr_key}"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        text = data.get("choices", [{}])[0].get("message", {}).get("content")
                        if text:
                            return 200, {
                                "success": True,
                                "text": text,
                                "usedProvider": "oxxy",
                                "keyIndexUsed": i,
                                "totalKeys": len(keys)
                            }
            except Exception as e:
                # Rotaciona para a próxima chave
                continue

    # 2. Fallback para o orquestrador/LLM nativo do Jarvis
    if orchestrator and hasattr(orchestrator, "llm_service"):
        try:
            full_prompt = f"{sys_prompt}\n\nUsuário:\n{prompt}"
            # Usa o método generate_content ou similar do LLMService do Jarvis
            llm = orchestrator.llm_service
            if hasattr(llm, "generate_text"):
                result = llm.generate_text(full_prompt)
                if result:
                    return 200, {
                        "success": True,
                        "text": result,
                        "usedProvider": "jarvis_native"
                    }
        except Exception as e:
            pass

    return 500, {
        "error": "Não foi possível gerar a resposta. Verifique as configurações de IA.",
        "success": False
    }


def handle_evolute_status_get() -> tuple[int, dict]:
    """
    Endpoint leve para o mini HUD do dashboard principal.
    Retorna os hábitos de hoje com estado done/isPriority/streak.
    """
    import datetime

    db_file = _get_db_file()
    try:
        raw = json.loads(db_file.read_text(encoding="utf-8")) if db_file.exists() else {}
        store = raw.get("data") or raw
        today = datetime.date.today().isoformat()
        from app.services.personal_habits import PersonalHabits
        result_habits = [
            {"id": h["id"], "name": h["name"], "done": h["completed_today"],
             "streak": h["current_streak"], "isPriority": h["isPriority"]}
            for h in PersonalHabits.list_habits(scheduled=True)
        ]

        done_count = sum(1 for h in result_habits if h["done"])
        total = len(result_habits)
        score = round((done_count / total) * 100) if total > 0 else 0

        water_key = f"lifeos_water_{today}"
        if water_key in store:
            water_ml = int(store[water_key] or 0)
        else:
            water_ml = sum(
                int(entry.get("ml", 0)) for entry in store.get("waterLog", [])
                if isinstance(entry, dict) and str(entry.get("date", "")).startswith(today)
            )

        vices_raw: list = store.get("vices", [])
        result_vices = []
        for v in vices_raw:
            if isinstance(v, dict):
                result_vices.append({
                    "id": v.get("id", ""),
                    "name": v.get("name", ""),
                    "streak": int(v.get("streak", 0)),
                    "longestStreak": int(v.get("longestStreak", 0)),
                })

        return 200, {
            "habits": result_habits,
            "waterMl": water_ml,
            "score": score,
            "vices": result_vices,
        }
    except Exception as err:
        return 500, {"error": str(err), "habits": [], "waterMl": 0, "score": 0, "vices": []}
