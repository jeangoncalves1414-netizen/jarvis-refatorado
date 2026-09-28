"""STM Filters (Semantic Transformation Modules) - Inspirado no G0DM0D3.

Filtra e normaliza as saídas geradas pelos LLMs para remover prolixidades,
hesitações, preâmbulos robóticos e saudações repetitivas antes de exibir ao usuário.
"""
from __future__ import annotations

import re


_ROBOTIC_PREAMBLES = [
    r"^com certeza[!.,]?\s*(aqui está|segue abaixo|conforme solicitado)?[:\s]*",
    r"^com prazer[!.,]?\s*(aqui está|segue|vou te ajudar)?[:\s]*",
    r"^claro[!.,]?\s*(aqui está|vou|posso te ajudar com isso)?[:\s]*",
    r"^como um modelo de linguagem (de ia|ia|treinado)?\s*,?\s*",
    r"^como um assistente de ia\s*,?\s*",
    r"^como uma inteligência artificial\s*,?\s*",
    r"^de acordo com (as minhas informações|meus conhecimentos|meus dados)\s*,?\s*",
    r"^olá[!.,]?\s*(como posso te ajudar hoje\??|em que posso ser útil\??)?\s*",
    r"^certamente[!.,]?\s*",
    r"^entendido[!.,]?\s*(aqui está|vou|posso)?[:\s]*",
]


class STMFilterEngine:
    """Motor de polimento semântico de respostas de LLM."""

    def __init__(self) -> None:
        self.preamble_patterns = [re.compile(p, re.IGNORECASE) for p in _ROBOTIC_PREAMBLES]

    def clean_text(self, text: str) -> str:
        """Limpa o texto do LLM removendo enrolações robóticas no início."""
        if not text or not text.strip():
            return text

        result = text.strip()

        # Aplica a limpeza de preâmbulo robótico no início da primeira linha
        for pattern in self.preamble_patterns:
            result = pattern.sub("", result).lstrip()

        # Remove linhas iniciais vazias geradas por cortes
        lines = result.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)

        return "\n".join(lines).strip()

    def filter_hesitations(self, text: str) -> str:
        """Substitui marcas de hesitação como 'acho que', 'talvez possa ser' por afirmativas diretas."""
        if not text:
            return text

        subs = [
            (r"\bacho que\b", "", re.IGNORECASE),
            (r"\bparece que talvez\b", "parece que", re.IGNORECASE),
            (r"\bse eu não me engano\b", "", re.IGNORECASE),
        ]
        res = text
        for pattern, repl, flags in subs:
            res = re.sub(pattern, repl, res, flags=flags)
        return res

    def process(self, text: str) -> str:
        """Aplica todas as transformações STM em sequência."""
        text = self.clean_text(text)
        text = self.filter_hesitations(text)
        return text


# Instância global do filtro STM
stm_filter = STMFilterEngine()
