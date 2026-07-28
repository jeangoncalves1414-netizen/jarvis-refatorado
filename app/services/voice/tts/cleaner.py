from __future__ import annotations

import re


def strip_text_for_speech(text: str) -> str:
    """
    Remove formatação Markdown, símbolos, URLs, marcadores [tool:...]
    e emojis que atrapalham a síntese de fala (TTS).
    """
    if not text:
        return ""

    t = text

    # Remove marcadores de ferramenta como [tool:open_windows_app:chrome] ou [tool:...]
    t = re.sub(r"\[tool:[^\]]+\]", "", t)

    # Remove blocos de código
    t = re.sub(r"```[\s\S]*?```", "", t)

    # Remove URLs
    t = re.sub(r"https?://\S+|www\.\S+", "", t)

    # Remove formatação básica de markdown (**bold**, *italic*, `code`, __underline__)
    t = t.replace("**", "").replace("__", "").replace("*", "").replace("`", "")

    # Remove títulos markdown (# Título)
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)

    # Remove links [texto](url) mantendo o texto
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)

    # Remove marcadores de lista (-, *, +, 1., 2.)
    t = re.sub(r"^\s*[-•>+]\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*\d+\.\s+", "", t, flags=re.MULTILINE)

    # Remove emojis comuns e caracteres de faixas especiais
    t = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]", "", t)

    # Normaliza quebras de linha e múltiplos espaços
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]+", " ", t)

    return t.strip()
