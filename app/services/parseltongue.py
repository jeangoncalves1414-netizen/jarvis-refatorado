"""
Parseltongue Sanitizer — inspirado no G0DM0D3
Limpador e normalizador rigoroso de respostas estruturadas (JSON / Markdown / Code blocks).
Garante extração limpa de código sem formatações corrompidas ou caracteres de controle inválidos.
"""
from __future__ import annotations

import json
import re
from typing import Any


class ParseltongueSanitizer:
    """Limpador e extrator de JSON / código."""

    @staticmethod
    def extract_json(raw_text: str) -> dict[str, Any] | list[Any] | None:
        """Extrai e valida o primeiro bloco JSON válido contido em uma string."""
        clean = raw_text.strip()
        clean = re.sub(r"```(?:json)?", "", clean).strip().rstrip("`").strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\}|\[.*\])", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def clean_markdown_code(raw_code: str) -> str:
        """Remove cercas de código markdown desnecessárias."""
        clean = raw_code.strip()
        if clean.startswith("```") and clean.endswith("```"):
            lines = clean.splitlines()
            if len(lines) >= 2:
                return "\n".join(lines[1:-1]).strip()
        return clean
