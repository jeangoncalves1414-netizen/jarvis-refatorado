"""Estado persistente do controle de clima exibido no painel.

Este serviço não controla um ar-condicionado físico. Ele preserva o alvo de
temperatura do painel até que uma integração residencial (por exemplo, Home
Assistant) seja configurada.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ClimateControlService:
    MIN_TEMPERATURE = 16
    MAX_TEMPERATURE = 30

    def __init__(self, state_path: str | Path = "data/climate_control.json") -> None:
        self.state_path = Path(state_path)

    def get_state(self) -> dict[str, Any]:
        default = {"target_c": 22, "integration": "panel"}
        try:
            if self.state_path.exists():
                saved = json.loads(self.state_path.read_text(encoding="utf-8"))
                value = int(saved.get("target_c", default["target_c"]))
                if self.MIN_TEMPERATURE <= value <= self.MAX_TEMPERATURE:
                    default["target_c"] = value
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return {"ok": True, **default}

    def set_target(self, value: Any) -> dict[str, Any]:
        try:
            target_c = int(value)
        except (TypeError, ValueError):
            return {"ok": False, "error": "A temperatura deve ser um número inteiro."}

        if not self.MIN_TEMPERATURE <= target_c <= self.MAX_TEMPERATURE:
            return {
                "ok": False,
                "error": f"A temperatura deve ficar entre {self.MIN_TEMPERATURE} e {self.MAX_TEMPERATURE}°C.",
            }

        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps({"target_c": target_c}, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            return {"ok": False, "error": f"Não foi possível salvar a temperatura: {exc}"}

        return {"ok": True, "target_c": target_c, "integration": "panel"}
