"""Serviço de Notificações Acionáveis do Windows 10/11.

Dispara notificações Toast nativas do Windows usando PowerShell WinRT
(ToastNotificationManager / XmlDocument) de forma 100% nativa sem dependências pip.
Suporta botões de ação rápida (deep-links) para interações como:
- Ouvir Briefing
- Ver Hábitos (abre janela life-os)
- Beber Água (+300ml)
- Abrir Link
"""
from __future__ import annotations

import base64
import html
import logging
import os
import subprocess
import threading
import urllib.parse
import webbrowser
from typing import Any

from app.core import ui_events
from app.storage import runtime_settings

logger = logging.getLogger(__name__)

# App ID padrão do Windows PowerShell para Toast Notification nativo sem empacotamento MSIX
DEFAULT_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"


def get_panel_base_url() -> str:
    """Retorna a URL base do servidor HTTP local do Jarvis."""
    port = os.getenv("APP_PORT", "8000")
    try:
        from app.config import get_settings
        settings = get_settings()
        if hasattr(settings, "port") and settings.port:
            port = str(settings.port)
    except Exception:
        pass
    return f"http://127.0.0.1:{port}"


def _escape_xml(text: Any) -> str:
    """Escapa caracteres especiais para XML de forma segura."""
    return html.escape(str(text or ""), quote=True)


def build_toast_xml(
    title: str,
    message: str,
    actions: list[dict[str, Any]] | None = None,
    urgency: str = "normal",
    sound: bool = True,
    base_url: str | None = None,
) -> str:
    """Monta o documento XML do Toast Notification Windows 10/11 com ações rápidas."""
    base = (base_url or get_panel_base_url()).rstrip("/")
    scenario = ' scenario="alarm"' if urgency in ("critical", "high", "urgent") else ""

    xml_lines = [
        f'<toast{scenario}>',
        '  <visual>',
        '    <binding template="ToastGeneric">',
        f'      <text>{_escape_xml(title)}</text>',
        f'      <text>{_escape_xml(message)}</text>',
        '    </binding>',
        '  </visual>',
    ]

    # Controle de som
    if not sound:
        xml_lines.append('  <audio silent="true"/>')

    # Ações interativas (botões de ação rápida)
    if actions:
        xml_lines.append('  <actions>')
        for act in actions[:5]:  # Windows suporta até 5 botões em notificações toast
            label = act.get("label") or act.get("text") or act.get("content") or "Ação"
            action_name = act.get("action") or act.get("name") or "default"
            url = act.get("url")

            if action_name in ("open_link", "open_url") and url:
                target_arg = url
            elif url and (str(url).startswith("http://") or str(url).startswith("https://")):
                target_arg = url
            else:
                # Constrói o deep link para o endpoint local do Jarvis
                params = {"action": action_name}
                for k, v in act.items():
                    if k not in ("label", "text", "content", "action", "name") and v is not None:
                        params[k] = v
                query_str = urllib.parse.urlencode(params)
                target_arg = f"{base}/api/notifications/action?{query_str}"

            xml_lines.append(
                f'    <action content="{_escape_xml(label)}" '
                f'arguments="{_escape_xml(target_arg)}" '
                f'activationType="protocol"/>'
            )
        xml_lines.append('  </actions>')

    xml_lines.append('</toast>')
    return "\n".join(xml_lines)


def _dispatch_powershell_toast(xml_content: str, app_id: str = DEFAULT_APP_ID) -> bool:
    """Executa o script PowerShell WinRT codificado em Base64 UTF-16LE."""
    ps_code = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$xml = @'
{xml_content}
'@

$doc = [Windows.Data.Xml.Dom.XmlDocument]::new()
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}')
$notifier.Show($toast)
"""
    try:
        b64 = base64.b64encode(ps_code.encode("utf-16le")).decode("ascii")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", b64],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if res.returncode == 0:
            return True
        logger.warning(f"PowerShell Toast retornou código {res.returncode}: {res.stderr}")
        return False
    except Exception as e:
        logger.error(f"Erro ao disparar ToastNotification via PowerShell: {e}")
        return False


def send_notification(
    title: str,
    message: str,
    actions: list[dict[str, Any]] | None = None,
    urgency: str = "normal",
    sound: bool | None = None,
    sync: bool = False,
) -> bool:
    """Envia uma notificação Toast acionável no Windows 10/11.

    Args:
        title: Título da notificação.
        message: Corpo de texto da mensagem.
        actions: Lista de botões interativos (ex: [{"label": "Beber Água", "action": "water", "amount": 300}]).
        urgency: Nível de urgência ("low", "normal", "high", "critical").
        sound: Se deve tocar som (None consulta as configurações em runtime).
        sync: Se True, executa sincronicamente; se False, dispara em thread separada.
    """
    settings = runtime_settings.get_notification_settings()
    if not settings.get("enabled", True):
        logger.info("Notificações do Windows desabilitadas pelo usuário.")
        return False

    use_sound = settings.get("sound", True) if sound is None else bool(sound)
    xml_content = build_toast_xml(
        title=title,
        message=message,
        actions=actions,
        urgency=urgency,
        sound=use_sound,
    )

    if sync:
        return _dispatch_powershell_toast(xml_content)

    thread = threading.Thread(
        target=_dispatch_powershell_toast,
        args=(xml_content,),
        name="windows-toast-dispatch",
        daemon=True,
    )
    thread.start()
    return True


def execute_notification_action(action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Processa a execução de uma ação interativa clicada na notificação ou chamada via API.

    Suporta:
    - "briefing" / "preview-morning": gera briefing matinal e opcionalmente dispara TTS / evento UI.
    - "habits" / "life-os": foca janela do Jarvis e abre a aba de hábitos no LifeOS.
    - "water": registra ingestão de água (padrão 300ml) no LifeOS e nos hábitos.
    - "open_link" / "open_url": abre link no navegador padrão do usuário.
    - "test": notificação de teste.
    """
    params = params or {}
    act = (action or "").strip().lower()

    if act in ("briefing", "preview-morning", "morning_briefing"):
        try:
            from app.services.briefing import generate_morning_briefing
            text = generate_morning_briefing()
            ui_events.publish({"type": "briefing", "text": text})

            # Tenta sintetizar voz em segundo plano se disponível
            def _speak_briefing():
                try:
                    from app.services.voice.tts.service import TTSService
                    tts = TTSService()
                    tts.speak(text)
                except Exception:
                    pass

            threading.Thread(target=_speak_briefing, daemon=True).start()
            return {"ok": True, "action": act, "message": "Briefing matinal gerado e iniciado.", "text": text}
        except Exception as e:
            logger.error(f"Erro ao processar ação de briefing: {e}")
            return {"ok": False, "action": act, "error": str(e)}

    if act in ("habits", "life-os", "lifeos"):
        try:
            # Tenta focar a janela do Jarvis no desktop
            try:
                from app.services.window_control import WindowControl
                wc = WindowControl()
                hwnd = wc.find_window("Jarvis")
                if hwnd:
                    wc.focus_window(hwnd)
            except Exception:
                pass

            tab = params.get("tab") or "habitos"
            event_payload = {"type": "open_window", "window_id": "life-os", "params": {"tab": tab}}
            ui_events.publish(event_payload)
            ui_events.publish({"type": "ui_window", "ui_window": {"window_id": "life-os", "params": {"tab": tab}}})
            return {"ok": True, "action": act, "message": "Janela LifeOS ativada com foco em hábitos."}
        except Exception as e:
            logger.error(f"Erro ao abrir LifeOS: {e}")
            return {"ok": False, "action": act, "error": str(e)}

    if act in ("water", "drink_water", "add_water"):
        try:
            amount = int(params.get("amount") or 300)
            from app.services.lifeos import LifeOSService
            result = LifeOSService.add_water(amount)

            # Notifica hábitos se houver regra conectada
            try:
                from app.services.habits import HabitService
                HabitService.on_event("water_added", {"amount": amount, "total": result.get("total_ml")})
            except Exception:
                pass

            ui_events.publish({
                "type": "water_added",
                "amount": amount,
                "total": result.get("total_ml"),
                "target": result.get("target_ml"),
            })
            return {
                "ok": True,
                "action": act,
                "message": f"+{amount}ml de água registrados com sucesso!",
                "data": result,
            }
        except Exception as e:
            logger.error(f"Erro ao registrar água: {e}")
            return {"ok": False, "action": act, "error": str(e)}

    if act in ("open_link", "open_url"):
        url = params.get("url") or params.get("link")
        if not url:
            return {"ok": False, "action": act, "error": "URL não fornecida."}
        try:
            webbrowser.open(str(url))
            return {"ok": True, "action": act, "message": f"Link aberto: {url}", "url": str(url)}
        except Exception as e:
            logger.error(f"Erro ao abrir URL: {e}")
            return {"ok": False, "action": act, "error": str(e)}

    if act in ("test", "test_notification"):
        sent = send_notification(
            title="Jarvis - Notificação de Teste",
            message="O sistema de notificações acionáveis do Windows está funcionando corretamente!",
            actions=[
                {"label": "Beber Água (+300ml)", "action": "water", "amount": 300},
                {"label": "Ver Hábitos", "action": "habits"},
            ],
            sync=True,
        )
        return {"ok": sent, "action": act, "message": "Notificação de teste disparada."}

    return {"ok": False, "action": act, "error": f"Ação desconhecida: '{action}'"}
