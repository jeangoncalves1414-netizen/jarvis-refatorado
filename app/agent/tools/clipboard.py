from __future__ import annotations

import os
import json
import time
from typing import Any
from .base import BaseTool, ToolResult

DATA_DIR = os.path.join(os.getcwd(), "data")
CLIPBOARD_FILE = os.path.join(DATA_DIR, "clipboard_history.json")

def add_clipboard_history(text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        history = []
        if os.path.exists(CLIPBOARD_FILE):
            with open(CLIPBOARD_FILE, "r", encoding="utf-8") as f:
                history = json.load(f).get("items", [])
        if history and history[-1].get("text") == text:
            return
        history.append({"text": text, "timestamp": time.time()})
        if len(history) > 20:
            history = history[-20:]
        with open(CLIPBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump({"items": history}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_clipboard_history(limit: int = 10) -> list[dict]:
    try:
        if os.path.exists(CLIPBOARD_FILE):
            with open(CLIPBOARD_FILE, "r", encoding="utf-8") as f:
                items = json.load(f).get("items", [])
                return items[-limit:]
    except Exception:
        pass
    return []


class ClipboardTool(BaseTool):
    @property
    def name(self) -> str:
        return "clipboard"

    @property
    def description(self) -> str:
        return "Lê, escreve ou consulta o histórico de cópias da área de transferência do sistema."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "copy", "history"],
                    "description": "read para ler atual; write/copy para copiar; history para ver últimas cópias.",
                },
                "text": {
                    "type": "string",
                    "description": "Texto a copiar para a área de transferência (obrigatório para write/copy).",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        try:
            import pyperclip
        except ImportError:
            return ToolResult(ok=False, message="pyperclip não instalado.")

        action = str(args.get("action", "read")).lower()

        if action == "history":
            items = get_clipboard_history(10)
            if not items:
                return ToolResult(ok=True, message="O histórico de área de transferência está vazio.")
            summary = "\n".join(f"{idx+1}. {item['text'][:80]}" for idx, item in enumerate(reversed(items)))
            return ToolResult(ok=True, message=f"Últimos itens copiados:\n{summary}", data={"history": items})

        if action in ("write", "copy"):
            text = str(args.get("text", ""))
            if not text:
                return ToolResult(ok=False, message="Texto vazio para copiar.")
            pyperclip.copy(text)
            add_clipboard_history(text)
            preview = text[:100] + ("..." if len(text) > 100 else "")
            return ToolResult(ok=True, message=f"Texto copiado com sucesso para a área de transferência: '{preview}'", data={"length": len(text)})
        else:
            content = pyperclip.paste()
            if content:
                add_clipboard_history(content)
            preview = (content or "")[:200]
            return ToolResult(ok=True, message=f"Conteúdo atual da área de transferência: {preview}", data={"content": content})


class NewsTool(BaseTool):
    DEFAULT_FEEDS = [
        "https://g1.globo.com/rss/g1/",
        "https://www.bbc.com/portuguese/index.xml",
    ]

    @property
    def name(self) -> str:
        return "news_reader"

    @property
    def description(self) -> str:
        return "Busca manchetes recentes de feeds RSS de notícias."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Número máximo de manchetes (padrão: 5).",
                },
                "feed_url": {
                    "type": "string",
                    "description": "URL do feed RSS (opcional).",
                },
            },
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        try:
            import feedparser
        except ImportError:
            return ToolResult(ok=False, message="feedparser não instalado.")

        limit = int(args.get("limit", 5))
        feed_url = args.get("feed_url") or self.DEFAULT_FEEDS[0]
        feed = feedparser.parse(feed_url)
        headlines = []
        for entry in feed.entries[:limit]:
            headlines.append({"title": entry.get("title", ""), "link": entry.get("link", "")})
        if not headlines:
            return ToolResult(ok=False, message="Nenhuma manchete encontrada.")
        summary = "; ".join(h["title"] for h in headlines)
        return ToolResult(ok=True, message=f"Manchetes: {summary}", data={"headlines": headlines})
