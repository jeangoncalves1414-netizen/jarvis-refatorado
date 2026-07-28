from __future__ import annotations

import re


def split_text_for_tts(text: str, max_chars: int = 1800) -> list[str]:
    """
    Divide o texto em blocos de até max_chars, preferindo separações
    em finais de frase ou parágrafos para reprodução fluida.
    """
    text = text.strip()
    if not text:
        return []

    max_c = max(100, min(8000, int(max_chars)))
    if len(text) <= max_c:
        return [text]

    chunks: list[str] = []
    rest = text
    guard = 0

    while rest and guard < 5000:
        guard += 1
        if len(rest) <= max_c:
            chunks.append(rest.strip())
            break

        window = rest[:max_c]
        end = max_c
        for sep in ("\n\n", ". ", "? ", "! ", "\n"):
            p = window.rfind(sep)
            if p >= max_c // 5:
                end = p + len(sep)
                break
        else:
            p = window.rfind(" ")
            if p >= max_c // 6:
                end = p + 1

        piece = rest[:end].strip()
        if not piece:
            end = max_c
            piece = rest[:end].strip()

        if piece:
            chunks.append(piece)
        rest = rest[end:].lstrip()

    return [c for c in chunks if c]
