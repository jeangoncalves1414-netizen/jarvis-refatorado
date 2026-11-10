from __future__ import annotations

import re

# Padrões de preâmbulos técnicos de ferramentas para remover de TTS
TOOL_PREAMBLE_PATTERNS = [
    re.compile(r"\bresultados?\s+das?\s+ferramentas?\s*:\s*", re.IGNORECASE),
    re.compile(r"\bresultados?\s+de\s+[a-zA-Z0-9_\-]+\s*:\s*", re.IGNORECASE),
    re.compile(r"\bresultado\s+da\s+pesquisa\s*:\s*", re.IGNORECASE),
    re.compile(r"\bsa[ií]da\s+d[ao]\s+ferramenta\s*:\s*", re.IGNORECASE),
    re.compile(r"\bferramenta\s+executada\s*:\s*", re.IGNORECASE),
    re.compile(r"\bexecutando\s+ferramenta\s*:\s*", re.IGNORECASE),
    re.compile(r"\bcomando\s+executado\s*:\s*", re.IGNORECASE),
    re.compile(r"\bsa[ií]da\s+do\s+terminal\s*:\s*", re.IGNORECASE),
    re.compile(r"\bnavegador\s+aberto\s+na\s+url\s*:\s*(?:https?://\S+)?", re.IGNORECASE),
    re.compile(r"\bp[aá]gina\s+aberta\s+em\s*:\s*(?:https?://\S+)?", re.IGNORECASE),
    re.compile(r"\bacessando(?:\s+a)?\s+url\s*:\s*(?:https?://\S+)?", re.IGNORECASE),
    re.compile(r"\b(?:no\s+link|do\s+link|pelo\s+link|no\s+site|da\s+fonte|a\s+fonte|o\s+link|a\s+url)\s*:\s*(?:https?://\S+|www\.\S+)?", re.IGNORECASE),
    re.compile(r"\b(?:link|url|fonte|href)\s*:\s*(?:https?://\S+|www\.\S+)?", re.IGNORECASE),
]


def sanitize_speech_text(text: str) -> str:
    """Higieniza o texto para síntese de fala (TTS) em chamadas de voz e assistente.

    - Remove marcadores [tool:...] e blocos de código
    - Remove preâmbulos de ferramentas ('Resultados das ferramentas:', 'Resultado de web_search:', etc.)
    - Remove URLs e referências brutas a links ('Link: https://...', 'URL: http://...', etc.)
    - Converte links markdown [texto](url) mantendo apenas o texto
    - Remove citações numéricas tipo [1], [2]
    - Remove cabeçalhos markdown (# Título) e formatação (negrito, itálico, crases)
    - Converte e limpa marcadores de lista e números repetitivos
    - Remove emojis e caracteres gráficos
    - Normaliza pontuações e espaços para garantir uma fala puramente conversacional e fluida
    """
    if not text:
        return ""

    t = text

    # Remove tags de ferramentas como [tool:open_windows_app:chrome]
    t = re.sub(r"\[tool:[^\]]+\]", "", t)

    # Remove blocos de código ```...```
    t = re.sub(r"```[\s\S]*?```", "", t)

    # Converte inline code `código` mantendo o texto interno
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = t.replace("`", "")

    # Remove preâmbulos técnicos de ferramentas
    for pattern in TOOL_PREAMBLE_PATTERNS:
        t = pattern.sub(" ", t)

    # Remove URLs restantes (http://, https://, www., etc.) para nunca serem soletradas pelo TTS
    t = re.sub(r"https?://\S+|www\.\S+", "", t)

    # Converte links markdown [texto](url) mantendo apenas o texto
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)

    # Remove citações numéricas [1], [2], etc.
    t = re.sub(r"\[\d+\]", "", t)

    # Remove títulos markdown (# Título)
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)

    # Remove formatação básica de markdown (**bold**, *italic*, __underline__, ~~strike~~)
    t = t.replace("**", "").replace("__", "").replace("~~", "").replace("*", "")

    # Converte marcadores de lista no início de linhas (-, *, +, •)
    t = re.sub(r"^\s*[-•>+]\s+", "", t, flags=re.MULTILINE)

    # Trata numerações repetitivas ou inline:
    # ' 1. Item ... 2. Item' -> ' Item. Item'
    t = re.sub(r"(?<=[.:;\n])\s*\d+[\.\)]\s*", " ", t)
    t = re.sub(r"^\s*\d+[\.\)]\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"\s+\d+[\.\)]\s+", ". ", t)

    # Remove emojis comuns e faixas de caracteres gráficos
    t = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]", "", t)

    # Normaliza quebras de linha e múltiplos espaços
    t = re.sub(r"\n{2,}", "\n", t)
    t = re.sub(r"[ \t]+", " ", t)

    # Limpeza de pontuação duplicada ou órfã após remoção de links/prefixos
    t = re.sub(r"\s*([:;])\s*([:;])+", r"\1", t)
    t = re.sub(r"\s*([.,;!?])\s*([.,;!?])+", r"\1", t)
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)

    # Remove dois-pontos, vírgulas, hífens ou espaços órfãos nas extremidades
    t = t.strip(" :;,-\t\n")

    return t


def strip_text_for_speech(text: str) -> str:
    """Compatibilidade retroativa com strip_text_for_speech, delegando para sanitize_speech_text."""
    return sanitize_speech_text(text)
