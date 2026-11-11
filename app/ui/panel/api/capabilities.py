"""Estado real de cada capacidade para a página Integrações (O1, PB5).

Para cada capacidade: se está configurada (chave, biblioteca, arquivo, ferramenta registrada),
se está alcançável (resultado da última chamada real desde que o servidor iniciou), o último
sucesso, a última falha e, quando desligada, o motivo. Nada aqui chama a rede nem executa
ferramenta; os segredos nunca aparecem, só se existem.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path
from typing import Any

from app.core.capability_health import capability_health, reachable_from


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _registered() -> tuple[set[str], set[str]]:
    """Ferramentas que o agente registra e as que o modo geral oferece ao modelo."""
    try:
        from app.agent.tools import registry as module
        from app.mcp.manager import mcp_manager
        names = set(module.GENERAL_TOOL_NAMES)
        registered = set(mcp_manager.get_registry().tools)
        return registered, names
    except Exception:
        return set(), set()


def _status(configured: bool | None, reachable: bool | None) -> str:
    if configured is False:
        return "off"
    if configured is None:
        return "unknown"
    if reachable is False:
        return "degraded"
    if reachable is True:
        return "healthy"
    return "configured"


def _item(capability_id: str, label: str, group: str, configured: bool | None, reason: str, *,
          provider: str | None = None, model: str | None = None, target: str = "Configurações") -> dict[str, Any]:
    record = capability_health.get(capability_id)
    reachable = reachable_from(record) if configured is not False else None
    return {
        "id": capability_id, "label": label, "group": group,
        "status": _status(configured, reachable),
        "configured": configured, "reachable": reachable,
        "last_success_at": record.get("last_success_at"),
        "last_failure_at": record.get("last_failure_at"),
        "last_failure_reason": record.get("last_failure_reason"),
        # Quem respondeu de fato na última chamada (O2); sem chamada, a rota configurada.
        "provider": record.get("provider") or provider,
        "model": record.get("model") or model,
        "latency_ms": record.get("latency_ms"),
        "fallback": record.get("fallback"),
        "reason": reason[:240],
        "target": target,
    }


_AI = (("chat", "Conversa"), ("tts", "Voz falada"), ("stt", "Transcrição de voz"), ("image", "Imagem"))


def _ai_capabilities() -> list[dict[str, Any]]:
    try:
        from app.storage.runtime_settings import resolve_ai_routes
        routes = resolve_ai_routes()
    except Exception:
        return [_item(key, label, "ia", None, "Configuração de IA indisponível.") for key, label in _AI]
    items = []
    for key, label in _AI:
        route = routes.get(key) or {}
        effective = route.get("effective") or {}
        configured = bool(route.get("configured"))
        reason = route.get("reason") or ""
        if not configured:
            reason = f"Desligado: {reason or 'sem chave para nenhum provedor desta capacidade.'}"
        items.append(_item(key, label, "ia", configured, reason, provider=effective.get("provider"), model=effective.get("model")))
    chat = routes.get("chat") or {}
    vision_on = bool(chat.get("configured"))
    items.append(_item(
        "vision", "Visão de tela e câmera", "ia", vision_on,
        "Usa a chave do provedor de conversa." if vision_on else "Desligado: sem chave do provedor de conversa.",
        provider=(chat.get("effective") or {}).get("provider"), target="Configurações",
    ))
    return items


def _devices() -> dict[str, Any]:
    try:
        from app.services.device_bridge import DeviceBridgeService
        devices = DeviceBridgeService().get_status().get("devices", [])
    except Exception as exc:
        item = _item("devices", "Dispositivos", "dispositivos", None, f"Não foi possível ler a ponte de dispositivos ({type(exc).__name__}).", target="Automações")
        item["status"] = "unavailable"
        return item
    online = sum(1 for device in devices if device.get("connected"))
    if not devices:
        return _item("devices", "Dispositivos", "dispositivos", False, "Desligado: nenhum dispositivo pareado.", target="Automações")
    item = _item("devices", "Dispositivos", "dispositivos", True, f"{len(devices)} pareado(s), {online} online.", target="Automações")
    item["status"] = "healthy" if online else "degraded"
    item["reachable"] = online > 0
    return item


def _integrations() -> list[dict[str, Any]]:
    registered, offered = _registered()

    def not_registered(tool: str) -> str | None:
        if tool not in registered:
            return "Desligado: a ferramenta não está registrada no agente."
        return None

    items: list[dict[str, Any]] = []

    # Spotify: teclas de mídia e URI spotify:, só no Windows.
    if os.name != "nt":
        items.append(_item("spotify", "Spotify", "integracao", False, "Desligado: o controle do Spotify só funciona no Windows."))
    else:
        exe = Path(os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"))
        if exe.exists():
            items.append(_item("spotify", "Spotify", "integracao", True, "Aplicativo encontrado; controle por teclas de mídia e links spotify:."))
        else:
            items.append(_item("spotify", "Spotify", "integracao", None, "Spotify.exe não encontrado em %APPDATA%\\Spotify; a versão da Microsoft Store não é detectada."))

    # WhatsApp: envio pelo mudslide via npx.
    if (reason := not_registered("whatsapp")):
        items.append(_item("whatsapp", "WhatsApp", "integracao", False, reason))
    elif shutil.which("npx"):
        items.append(_item("whatsapp", "WhatsApp", "integracao", True, "Envio pelo mudslide (npx). O login do WhatsApp só é confirmado no primeiro envio."))
    else:
        items.append(_item("whatsapp", "WhatsApp", "integracao", False, "Desligado: npx (Node.js) não encontrado; o envio usa o mudslide."))

    # Telegram: biblioteca python-telegram-bot e token.
    if (reason := not_registered("telegram_bot")):
        items.append(_item("telegram", "Telegram", "integracao", False, reason))
    elif not _has_module("telegram"):
        items.append(_item("telegram", "Telegram", "integracao", False, "Desligado: biblioteca python-telegram-bot não instalada."))
    elif not os.getenv("TELEGRAM_BOT_TOKEN"):
        items.append(_item("telegram", "Telegram", "integracao", False, "Desligado: TELEGRAM_BOT_TOKEN não configurado."))
    else:
        chat = "com" if os.getenv("TELEGRAM_CHAT_ID") else "sem"
        items.append(_item("telegram", "Telegram", "integracao", True, f"Token configurado, {chat} chat padrão."))

    # Kasa: biblioteca python-kasa.
    if (reason := not_registered("kasa_control")):
        items.append(_item("kasa", "Tomadas Kasa", "integracao", False, reason, target="Automações"))
    elif not _has_module("kasa"):
        items.append(_item("kasa", "Tomadas Kasa", "integracao", False, "Desligado: biblioteca python-kasa não instalada.", target="Automações"))
    else:
        items.append(_item("kasa", "Tomadas Kasa", "integracao", True, "Biblioteca instalada; os aparelhos são descobertos na rede local a cada uso.", target="Automações"))

    # Home Assistant (fase contexto 3)
    try:
        from app.services import home_assistant as ha_module
        if not ha_module.is_configured():
            items.append(_item("home_assistant", "Home Assistant", "integracao", False, "Desligado: não configurado.", target="Casa"))
        else:
            host = ha_module._host(ha_module._config()["url"])
            items.append(_item("home_assistant", "Home Assistant", "integracao", True, f"Conectado a {host}.", target="Casa"))
    except Exception:
        items.append(_item("home_assistant", "Home Assistant", "integracao", False, "Desligado: não configurado.", target="Casa"))

    # MCP: arquivo de servidores.
    if (reason := not_registered("mcp")):
        items.append(_item("mcp", "Servidores MCP", "integracao", False, reason))
    else:
        try:
            from app.mcp.config import load_server_configs
            servers = load_server_configs()
        except Exception:
            servers = {}
        suffix = "" if "mcp" in offered else " A ferramenta não é oferecida no modo geral do chat."
        if servers:
            items.append(_item("mcp", "Servidores MCP", "integracao", True, f"{len(servers)} servidor(es) em data/mcp_servers.json.{suffix}"))
        else:
            items.append(_item("mcp", "Servidores MCP", "integracao", False, f"Desligado: nenhum servidor em data/mcp_servers.json.{suffix}"))

    # Composio: código existe, mas a ferramenta não é registrada.
    parts = ["a ferramenta não está registrada no agente"]
    if not os.getenv("COMPOSIO_API_KEY"):
        parts.append("COMPOSIO_API_KEY não configurada")
    items.append(_item("composio", "Composio (Gmail, Calendar, Notion, Slack, GitHub, Jira)", "integracao", False, "Desligado: " + "; ".join(parts) + "."))

    # Calendário local.
    if (reason := not_registered("calendar")):
        items.append(_item("calendar", "Calendário local", "integracao", False, reason, target="Calendário"))
    else:
        items.append(_item("calendar", "Calendário local", "integracao", True, "Calendário do próprio app, sem conta externa.", target="Calendário"))
    return items


def build_capabilities() -> list[dict[str, Any]]:
    return [*_ai_capabilities(), _devices(), *_integrations()]


def capabilities_meta() -> dict[str, Any]:
    return {"health_since": capability_health.started_at}
