from __future__ import annotations

import os
import threading
from typing import Any
from .base import BaseTool, ToolResult

_telegram_daemon_thread: threading.Thread | None = None
_telegram_stop_event: threading.Event = threading.Event()


def _start_telegram_daemon(token: str, authorized_ids: list[int], on_message_callback) -> None:
    """Inicia o bot do Telegram em thread separada."""
    global _telegram_daemon_thread, _telegram_stop_event
    if _telegram_daemon_thread and _telegram_daemon_thread.is_alive():
        return  # Já está rodando

    _telegram_stop_event.clear()

    def _run():
        try:
            from telegram import Update
            from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

            async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id not in authorized_ids:
                    await update.message.reply_text("🚫 Não autorizado.")
                    return
                await update.message.reply_text("⚡ Jarvis conectado via Telegram. Como posso ajudar?")

            async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id not in authorized_ids:
                    await update.message.reply_text("🚫 Não autorizado.")
                    return
                text = update.message.text or ""
                if on_message_callback:
                    reply = on_message_callback(text, update.effective_user.id)
                    await update.message.reply_text(reply or "✅ Comando recebido.")

            app = ApplicationBuilder().token(token).build()
            app.add_handler(CommandHandler("start", start_cmd))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
            app.run_polling(stop_signals=None)
        except Exception as e:
            print(f"[TelegramBot] Erro: {e}")

    _telegram_daemon_thread = threading.Thread(target=_run, daemon=True, name="TelegramBotDaemon")
    _telegram_daemon_thread.start()


class TelegramBotTool(BaseTool):
    """
    Telegram Bot — Controle remoto do Jarvis via mensagens no Telegram.
    Permite enviar comandos, receber notificações e delegar tarefas de forma assíncrona.
    """

    @property
    def name(self) -> str:
        return "telegram_bot"

    @property
    def description(self) -> str:
        return "Envia uma mensagem de notificação via Telegram, ou inicia/para o bot Telegram para controle remoto do Jarvis."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["send", "start_bot", "stop_bot", "status"],
                    "description": "Ação: send (enviar mensagem), start_bot (iniciar daemon), stop_bot, status.",
                },
                "message": {
                    "type": "string",
                    "description": "Mensagem a enviar (para action=send).",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Chat ID do destino (obrigatório para send). Pode ser configurado no .env como TELEGRAM_CHAT_ID.",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "status")).lower()
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id_env = os.environ.get("TELEGRAM_CHAT_ID", "")

        if action == "status":
            running = _telegram_daemon_thread is not None and _telegram_daemon_thread.is_alive()
            return ToolResult(
                ok=True,
                message=f"Bot Telegram: {'🟢 Ativo' if running else '🔴 Parado'}.",
                data={"running": running, "token_configured": bool(token)},
            )

        if action == "stop_bot":
            _telegram_stop_event.set()
            return ToolResult(ok=True, message="Sinal de parada enviado ao bot Telegram.")

        if not token:
            return ToolResult(ok=False, message="TELEGRAM_BOT_TOKEN não configurado no arquivo .env.")

        if action == "start_bot":
            try:
                authorized_raw = os.environ.get("TELEGRAM_AUTHORIZED_IDS", "")
                authorized_ids = [int(x) for x in authorized_raw.split(",") if x.strip().isdigit()]
                _start_telegram_daemon(token, authorized_ids, on_message_callback=None)
                return ToolResult(ok=True, message="Bot Telegram iniciado com sucesso em background.")
            except ImportError:
                return ToolResult(ok=False, message="Biblioteca 'python-telegram-bot' não instalada. Execute: pip install python-telegram-bot")
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao iniciar bot Telegram: {e}")

        if action == "send":
            import asyncio
            message = str(args.get("message", "")).strip()
            chat_id = str(args.get("chat_id", chat_id_env)).strip()
            if not message:
                return ToolResult(ok=False, message="Mensagem em branco.")
            if not chat_id:
                return ToolResult(ok=False, message="chat_id não fornecido e TELEGRAM_CHAT_ID não configurado no .env.")

            try:
                from telegram import Bot
                async def _send():
                    bot = Bot(token=token)
                    await bot.send_message(chat_id=chat_id, text=message)
                asyncio.run(_send())
                return ToolResult(ok=True, message=f"Mensagem enviada via Telegram para chat {chat_id}.")
            except ImportError:
                return ToolResult(ok=False, message="Biblioteca 'python-telegram-bot' não instalada.")
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao enviar mensagem Telegram: {e}")

        return ToolResult(ok=False, message=f"Ação '{action}' inválida.")
