"""Mode resolver - detects operation mode from user text."""

from __future__ import annotations

import re
import unicodedata

from app.agent.runtime_modes import AgentMode, ModeResolution


_SHORT_GREETINGS = {
    "oi", "ola", "olá", "hey", "hi", "hello",
    "bom dia", "boa tarde", "boa noite"
}


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_marks.lower()


class ModeResolver:
    """Detects the appropriate operation mode from user input."""
    
    def resolve(self, text: str) -> ModeResolution:
        raw = (text or "").strip()
        folded = _fold(raw)
        compact = folded.strip(" !?.\t\r\n")

        if compact in {_fold(x) for x in _SHORT_GREETINGS}:
            return ModeResolution(AgentMode.CHAT, 1.0, "short greeting")

        explicit = bool(re.search(r"\b(modo|mode|entra no modo)\b", folded))
        open_window = bool(re.search(r"\b(abre|abrir|mostra|mostrar|janela|painel)\b", folded))

        # Priority mode detection
        mode_checks = [
            (AgentMode.FILES, ["arquivo", "pasta", "downloads", "documentos", "apaga", "delete", "deleta", "limpa"], 0.82),
            (AgentMode.PC, ["abre", "abrir", "fecha", "fechar", "spotify", "chrome", "notepad", "bloco de notas"], 0.78),
            (AgentMode.WEB, ["pesquise", "pesquisar", "procure", "buscar", "clima", "cotacao"], 0.72),
            (AgentMode.VISION, ["tela", "monitor", "o que voce ve", "o que aparece"], 0.76),
        ]

        for mode, keywords, confidence in mode_checks:
            if self._has_any(folded, keywords):
                return ModeResolution(mode, confidence, f"{mode.value} keywords", explicit, open_window=open_window)

        return ModeResolution(AgentMode.CHAT, 0.55, "default chat")

    @staticmethod
    def _has_any(text: str, needles: list[str]) -> bool:
        return any(needle in text for needle in needles)
