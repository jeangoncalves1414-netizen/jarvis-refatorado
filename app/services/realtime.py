"""Serviço de busca de dados em tempo real (Clima, Notícias, Cotações e Feriados)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any


class RealTimeService:
    """Busca dados atualizados em tempo real de APIs públicas e gratuitas sem necessidade de chave."""

    @staticmethod
    def get_weather(city: str = "") -> dict[str, Any]:
        """Obtém dados meteorológicos de wttr.in em formato JSON."""
        encoded_city = urllib.parse.quote(city.strip()) if city.strip() else ""
        url = f"https://wttr.in/{encoded_city}?format=j1&lang=pt" if encoded_city else "https://wttr.in/?format=j1&lang=pt"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            current = data.get("current_condition", [{}])[0]
            weather_desc = current.get("lang_pt", [{}])[0].get("value") or current.get("weatherDesc", [{}])[0].get("value", "Desconhecido")
            nearest_area = data.get("nearest_area", [{}])[0]
            area_name = nearest_area.get("areaName", [{}])[0].get("value", city or "Sua localização")
            region_name = nearest_area.get("region", [{}])[0].get("value", "")

            forecast_today = data.get("weather", [{}])[0]
            max_temp = forecast_today.get("maxtempC", "N/A")
            min_temp = forecast_today.get("mintempC", "N/A")

            return {
                "ok": True,
                "city": (f"{area_name}, {region_name}" if region_name else area_name).strip(),
                "temp_c": current.get("temp_C"),
                "feels_like_c": current.get("FeelsLikeC"),
                "description": weather_desc,
                "humidity": current.get("humidity"),
                "wind_kmh": current.get("windspeedKmph"),
                "temp_max": max_temp,
                "temp_min": min_temp,
            }
        except Exception as e:
            return {"ok": False, "error": f"Erro ao buscar clima: {e}"}

    @staticmethod
    def get_finance() -> dict[str, Any]:
        """Obtém cotações atuais de Dólar, Euro e Bitcoin via AwesomeAPI."""
        url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-BRL"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            usd = data.get("USDBRL", {})
            eur = data.get("EURBRL", {})
            btc = data.get("BTCBRL", {})

            return {
                "ok": True,
                "currencies": {
                    "USD": {
                        "name": "Dólar Comercial",
                        "bid": float(usd.get("bid", 0)),
                        "pctChange": float(usd.get("pctChange", 0)),
                        "high": float(usd.get("high", 0)),
                        "low": float(usd.get("low", 0)),
                    },
                    "EUR": {
                        "name": "Euro",
                        "bid": float(eur.get("bid", 0)),
                        "pctChange": float(eur.get("pctChange", 0)),
                        "high": float(eur.get("high", 0)),
                        "low": float(eur.get("low", 0)),
                    },
                    "BTC": {
                        "name": "Bitcoin",
                        "bid": float(btc.get("bid", 0)),
                        "pctChange": float(btc.get("pctChange", 0)),
                        "high": float(btc.get("high", 0)),
                        "low": float(btc.get("low", 0)),
                    },
                },
            }
        except Exception as e:
            return {"ok": False, "error": f"Erro ao buscar cotações: {e}"}

    @staticmethod
    def get_news(limit: int = 5) -> dict[str, Any]:
        """Obtém últimas notícias do RSS oficial do G1 Brasil."""
        url = "https://g1.globo.com/rss/g1/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw_xml = resp.read()

            root = ET.fromstring(raw_xml)
            items = root.findall(".//item")
            news_list = []

            for item in items[:limit]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                if title:
                    news_list.append({
                        "title": title,
                        "link": link,
                        "pub_date": pub_date
                    })

            return {"ok": True, "source": "G1 Globo", "news": news_list}
        except ET.ParseError as e:
            return {"ok": False, "error": f"Feed do G1 retornou conteúdo inválido (não-XML): {e}"}
        except Exception as e:
            return {"ok": False, "error": f"Erro ao buscar notícias: {e}"}

    @staticmethod
    def get_holidays(year: int | None = None) -> dict[str, Any]:
        """Obtém os feriados nacionais do Brasil via BrasilAPI."""
        target_year = year or datetime.now().year
        url = f"https://brasilapi.com.br/api/feriados/v1/{target_year}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            return {
                "ok": True,
                "year": target_year,
                "total": len(data),
                "holidays": data
            }
        except Exception as e:
            return {"ok": False, "error": f"Erro ao buscar feriados: {e}"}
