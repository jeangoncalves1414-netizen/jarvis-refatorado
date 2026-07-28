from __future__ import annotations

# Termos que o Whisper inventa em momentos de silêncio ou ruído baixo em PT-BR
HARD_HALLUCINATIONS = [
    "legenda por",
    "legendas por",
    "sônia ruberti",
    "sonia ruberti",
    "transmissão por",
    "geraldump",
    "geral dump",
    "cachou",
    "inscreva-se",
    "deixe seu like",
    "curta o vídeo",
    "obrigado por assistir",
]

SOFT_HALLUCINATIONS = [
    "obrigado",
    "obrigada",
    "valeu",
    "tchau",
    "e aí",
    "e ai",
    "oi",
    "hmmm",
    "hum",
    "ok",
    "ah",
    "eh",
    "teste 1 2 3",
    "testando 1 2 3",
]


def filter_stt_hallucinations(text: str) -> str:
    """
    Filtra alucinações comuns geradas por modelos Whisper em áudios com ruído
    ou silêncio prolongado. Retorna string vazia se o áudio for considerado ruído.
    """
    if not text:
        return ""

    raw_text = text.strip()
    lowered = (
        raw_text.lower()
        .replace(".", "")
        .replace("!", "")
        .replace("?", "")
        .replace(",", "")
        .strip()
    )

    # 1. Se contiver QUALQUER termo "hard", é 100% lixo de STT de silêncio
    if any(h in lowered for h in HARD_HALLUCINATIONS):
        return ""

    # 2. Se for uma alucinação de palavra única isolada por ruído de impacto no microfone (ex: "tchau", "obrigado")
    SINGLE_WORD_HALLUCINATIONS = {"tchau", "obrigado", "obrigada", "valeu", "hmmm", "hum", "ah", "eh"}
    if lowered in SINGLE_WORD_HALLUCINATIONS:
        return ""

    return raw_text
