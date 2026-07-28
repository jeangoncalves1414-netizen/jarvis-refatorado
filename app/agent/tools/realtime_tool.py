"""Ferramenta de busca de dados em tempo real (Clima, Notícias, Cotações e Feriados)."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.services.realtime import RealTimeService


class RealTimeTool(BaseTool):
    @property
    def name(self) -> str:
        return "realtime"

    @property
    def description(self) -> str:
        return (
            "Obtém dados dinâmicos em tempo real do mundo físico: clima/temperatura de qualquer cidade, "
            "últimas notícias do G1, cotações financeiras (Dólar, Euro, Bitcoin) e feriados nacionais do Brasil."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_weather", "get_news", "get_finance", "get_holidays"],
                    "description": (
                        "Ação a realizar: 'get_weather' (clima/temperatura), 'get_news' (notícias do dia), "
                        "'get_finance' (cotações Dólar/Euro/Bitcoin), 'get_holidays' (feriados nacionais)."
                    ),
                },
                "city": {
                    "type": "string",
                    "description": "Nome da cidade para consulta do clima (ex: 'São Paulo', 'Rio de Janeiro'). Se omitido, usa localização atual.",
                },
                "year": {
                    "type": "integer",
                    "description": "Ano para consultar os feriados nacionais (ex: 2026). Padrão é o ano atual.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Número de notícias a retornar (padrão: 5).",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action")
        if not action:
            return ToolResult(ok=False, message="Ação é obrigatória.")

        if action == "get_weather":
            city = str(args.get("city", "") or "").strip()
            res = RealTimeService.get_weather(city)
            if not res.get("ok"):
                return ToolResult(ok=False, message=res.get("error", "Erro ao obter clima."))
            msg = (
                f"Clima em {res['city']}:\n"
                f"- Temperatura: {res['temp_c']}°C (Sensação: {res['feels_like_c']}°C)\n"
                f"- Condição: {res['description']}\n"
                f"- Mínima/Máxima: {res['temp_min']}°C / {res['temp_max']}°C\n"
                f"- Umidade: {res['humidity']}% | Vento: {res['wind_kmh']} km/h"
            )
            return ToolResult(ok=True, message=msg, data=res)

        elif action == "get_finance":
            res = RealTimeService.get_finance()
            if not res.get("ok"):
                return ToolResult(ok=False, message=res.get("error", "Erro ao obter cotações."))
            currencies = res.get("currencies", {})
            lines = ["Cotações em tempo real:"]
            for code, item in currencies.items():
                change_sign = "+" if item["pctChange"] >= 0 else ""
                lines.append(
                    f"- {item['name']} ({code}): R$ {item['bid']:.2f} ({change_sign}{item['pctChange']:.2f}%)"
                )
            return ToolResult(ok=True, message="\n".join(lines), data=res)

        elif action == "get_news":
            limit = int(args.get("limit", 5) or 5)
            res = RealTimeService.get_news(limit=limit)
            if not res.get("ok"):
                return ToolResult(ok=False, message=res.get("error", "Erro ao obter notícias."))
            news = res.get("news", [])
            lines = [f"Principais notícias ({res['source']}):"]
            for idx, item in enumerate(news, 1):
                lines.append(f"{idx}. {item['title']}")
            return ToolResult(ok=True, message="\n".join(lines), data=res)

        elif action == "get_holidays":
            year = args.get("year")
            res = RealTimeService.get_holidays(year=year)
            if not res.get("ok"):
                return ToolResult(ok=False, message=res.get("error", "Erro ao obter feriados."))
            holidays = res.get("holidays", [])
            lines = [f"Feriados Nacionais de {res['year']} ({res['total']} feriados):"]
            for item in holidays:
                date_fmt = item.get("date", "")
                name = item.get("name", "")
                lines.append(f"- {date_fmt}: {name}")
            return ToolResult(ok=True, message="\n".join(lines), data=res)

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
