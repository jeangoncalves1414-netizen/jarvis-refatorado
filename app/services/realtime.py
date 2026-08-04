"""Serviço de busca de dados em tempo real (Clima, Notícias, Cotações e Feriados)."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any


class RealTimeService:
    """Busca dados atualizados em tempo real de APIs públicas e gratuitas sem necessidade de chave."""

    _WEATHER_CODES = {
        0: "Céu limpo", 1: "Predominantemente limpo", 2: "Parcialmente nublado",
        3: "Nublado", 45: "Neblina", 48: "Neblina com geada", 51: "Garoa leve",
        53: "Garoa", 55: "Garoa intensa", 61: "Chuva leve", 63: "Chuva",
        65: "Chuva forte", 71: "Neve leve", 73: "Neve", 75: "Neve forte",
        80: "Pancadas leves", 81: "Pancadas", 82: "Pancadas fortes",
        95: "Trovoadas", 96: "Trovoadas com granizo", 99: "Trovoadas fortes com granizo",
    }

    @staticmethod
    def _get_json(url: str, timeout: int = 6) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": "Jarvis-Rebuild/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def _resolve_city(cls, city: str) -> str:
        requested = city.strip() or os.getenv("WEATHER_CITY", "").strip()
        if requested:
            return requested
        try:
            location = cls._get_json("https://ipapi.co/json/", timeout=4)
            return str(location.get("city", "")).strip()
        except Exception:
            return ""

    @classmethod
    def get_weather(cls, city: str = "") -> dict[str, Any]:
        """Obtém clima pelo Open-Meteo, uma API gratuita e sem chave."""
        requested_city = cls._resolve_city(city)
        if not requested_city:
            return {
                "ok": False,
                "error": "Informe uma cidade ou defina WEATHER_CITY no arquivo .env.",
            }

        try:
            encoded_city = urllib.parse.quote(requested_city)
            geocoding = cls._get_json(
                "https://geocoding-api.open-meteo.com/v1/search"
                f"?name={encoded_city}&count=1&language=pt&format=json"
            )
            result = (geocoding.get("results") or [None])[0]
            if not result:
                return {"ok": False, "error": f"Cidade não encontrada: {requested_city}."}

            latitude, longitude = result["latitude"], result["longitude"]
            forecast = cls._get_json(
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={latitude}&longitude={longitude}"
                "&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code"
                "&daily=temperature_2m_max,temperature_2m_min&forecast_days=1&timezone=auto"
            )
            current = forecast.get("current", {})
            daily = forecast.get("daily", {})
            place = ", ".join(part for part in (result.get("name"), result.get("admin1")) if part)

            return {
                "ok": True,
                "city": place or requested_city,
                "temp_c": current.get("temperature_2m"),
                "feels_like_c": current.get("apparent_temperature"),
                "description": cls._WEATHER_CODES.get(current.get("weather_code"), "Condições indisponíveis"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_kmh": current.get("wind_speed_10m"),
                "temp_max": (daily.get("temperature_2m_max") or ["N/A"])[0],
                "temp_min": (daily.get("temperature_2m_min") or ["N/A"])[0],
            }
        except Exception as exc:
            return {"ok": False, "error": f"Erro ao buscar clima: {exc}"}

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
