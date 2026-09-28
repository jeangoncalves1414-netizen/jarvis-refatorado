"""
Scout Intent Classifier — inspirado no Ada-SI
Classificador ultrarrápido de intenção pré-execução para escolher o modelo/ferramenta ideal sem desperdiçar tokens.
"""
from __future__ import annotations

import re
from typing import Any


class ScoutIntentClassifier:
    """Classificador leve de intenção do usuário."""

    INTENT_PATTERNS = {
        "code": [r"\b(python|javascript|typescript|c\+\+|html|css|sql|function|def|code|bug|error|refactor)\b"],
        "math_calc": [r"\b(calcule|quanto e|soma|multiplique|raiz|porcentagem|equacao)\b"],
        "media_cinema": [r"\b(filme|serie|cinema|assistir|player|play|episodio|temporada)\b"],
        "mobile_control": [r"\b(celular|android|adb|app|clique no celular|instalar apk)\b"],
        "file_system": [r"\b(arquivo|pasta|pasta downloads|deletar|mover|copiar|pesquisar arquivo)\b"],
        "general_chat": [],
    }

    @classmethod
    def classify(cls, query: str) -> dict[str, Any]:
        raw = query.lower()
        for category, patterns in cls.INTENT_PATTERNS.items():
            for p in patterns:
                if re.search(p, raw):
                    return {"category": category, "confidence": 0.9, "suggested_mode": category}

        return {"category": "general_chat", "confidence": 0.7, "suggested_mode": "general"}
