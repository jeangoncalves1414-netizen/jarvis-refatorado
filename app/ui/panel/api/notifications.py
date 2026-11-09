"""Endpoint para recepção e disparo de notificações acionáveis do Windows.

Endpoints:
- POST /api/notifications/action : Executa uma ação de notificação (briefing, habits, water, open_link, test).
- GET  /api/notifications/action : Permite ativação via deep-link de protocolo HTTP do Windows.
- POST /api/notifications/test   : Dispara notificação de teste interativa nativa.
- POST /api/notifications/send   : Dispara notificação customizada via API.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qs, urlsplit

from app.services.windows_notifications import execute_notification_action, send_notification

logger = logging.getLogger(__name__)

HTML_ACTION_RESPONSE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Jarvis · Ação de Notificação</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #0b0f19;
      color: #e2e8f0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }}
    .card {{
      background: #111827;
      border: 1px solid #00daf840;
      box-shadow: 0 10px 25px -5px rgba(0, 218, 248, 0.15);
      border-radius: 12px;
      padding: 28px 36px;
      max-width: 440px;
      text-align: center;
    }}
    h2 {{
      color: #00daf8;
      margin-top: 0;
      margin-bottom: 12px;
      font-size: 20px;
      letter-spacing: -0.02em;
    }}
    p {{
      color: #94a3b8;
      font-size: 14px;
      line-height: 1.5;
      margin-bottom: 20px;
    }}
    .close-hint {{
      font-size: 12px;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h2>Jarvis · Ação Concluída</h2>
    <p>{message}</p>
    <div class="close-hint">Esta janela fechará automaticamente.</div>
  </div>
  <script>
    setTimeout(function() {{
      window.close();
    }}, 1500);
  </script>
</body>
</html>
"""


def handle_notifications_get(parts: list[str], handler: Any) -> tuple[int, Any] | None:
    """Manipula GET em /api/notifications/*."""
    if len(parts) < 3 or parts[:2] != ["api", "notifications"]:
        return None

    sub = parts[2]
    if sub == "action":
        url = getattr(handler, "path", "") or ""
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)

        action = query.get("action", [""])[0]
        params: dict[str, Any] = {}
        for k, v in query.items():
            if k != "action":
                params[k] = v[0] if len(v) == 1 else v

        res = execute_notification_action(action, params)

        # Se a requisição veio de um clique do usuário abrindo navegador (protocol activation)
        accept = getattr(handler, "headers", {}).get("Accept", "")
        if "text/html" in accept:
            msg = res.get("message") or ("Ação executada com sucesso." if res.get("ok") else res.get("error", "Erro ao executar ação."))
            body = HTML_ACTION_RESPONSE.format(message=msg).encode("utf-8")
            return 200, body

        return (200 if res.get("ok") else 400), res

    return None


def handle_notifications_post(path: str, body: bytes, _handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Manipula POST em /api/notifications/*."""
    if not path.startswith("/api/notifications"):
        return None

    clean_path = urlsplit(path).path.rstrip("/")
    pieces = [p for p in clean_path.split("/") if p]
    if len(pieces) < 3 or pieces[:2] != ["api", "notifications"]:
        return None

    sub = pieces[2]

    try:
        raw_text = body.decode("utf-8") if body else "{}"
        payload = json.loads(raw_text) if raw_text.strip() else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"ok": False, "error": "JSON inválido."}

    if sub == "action":
        action = payload.get("action")
        if not action:
            return 400, {"ok": False, "error": "Campo 'action' é obrigatório."}
        params = payload.get("params")
        if not isinstance(params, dict):
            params = {k: v for k, v in payload.items() if k != "action"}
        res = execute_notification_action(action, params)
        status = 200 if res.get("ok") else 400
        return status, res

    if sub == "test":
        sent = send_notification(
            title="Jarvis · Teste de Notificação",
            message="Notificações acionáveis do Windows ativas e prontas para uso!",
            actions=[
                {"label": "Beber Água (+300ml)", "action": "water", "amount": 300},
                {"label": "Ver Hábitos", "action": "habits"},
                {"label": "Ouvir Briefing", "action": "briefing"},
            ],
            sync=True,
        )
        return 200, {"ok": sent, "message": "Notificação de teste disparada."}

    if sub == "send":
        title = payload.get("title") or "Jarvis"
        message = payload.get("message") or ""
        actions = payload.get("actions") or []
        urgency = payload.get("urgency") or "normal"
        sound = payload.get("sound")
        sent = send_notification(
            title=title,
            message=message,
            actions=actions if isinstance(actions, list) else None,
            urgency=urgency,
            sound=sound,
            sync=True,
        )
        return 200, {"ok": sent, "message": "Notificação processada."}

    return None

