"""Automatic emotion cues for Fish Audio S2 speech.

Fish S2 accepts natural-language cues in square brackets (for example
``[warmly]`` or ``[concerned]``).  The chat text must remain untouched, so
this module only decorates the private string sent to the Fish provider.
The classifier is deliberately deterministic and conservative: it adds a
cue only when the sentence clearly suggests an emotion or speaking style.
"""
from __future__ import annotations

import re


_SENTENCE_RE = re.compile(r"([^.!?…]+(?:[.!?…]+|$))", re.UNICODE)
_CUE_RE = re.compile(r"^\s*(?:\[[^\]]+\]|\([^)]{2,40}\))\s*", re.UNICODE)


def _cue_for_sentence(sentence: str) -> str | None:
    folded = sentence.casefold()
    if re.search(r"\b(bom dia|boa tarde|boa noite|olá|oi|bem-vindo|bem-vinda)\b", folded):
        return "[warmly]"
    if "?" in sentence or re.search(r"\b(será que|pode me dizer|quer que|posso|como posso)\b", folded):
        return "[curious]"
    if re.search(r"\b(erro|falha|atenção|cuidado|perigo|indisponível|não foi possível|problema|risco)\b", folded):
        return "[concerned]"
    if re.search(r"\b(desculpa|sinto muito|infelizmente|lamento)\b", folded):
        return "[apologetic]"
    if re.search(r"\b(parabéns|excelente|ótimo|ótima|perfeito|perfeita|incrível|conseguimos|sucesso)\b", folded) or "!" in sentence:
        return "[excited]"
    if re.search(r"\b(sem problema|pode ficar tranquilo|tudo certo|vou cuidar|fica tranquilo|entendo)\b", folded):
        return "[reassuring]"
    return None


def add_emotion_cues(text: str, *, enabled: bool = True, model: str = "s2.1-pro-free") -> str:
    """Return *text* with conservative, sentence-level Fish emotion cues.

    Existing cues are preserved. S2 models use ``[brackets]``; S1 uses the
    older parenthesis syntax. The returned value is intended only for the
    provider request, never for chat history or the visible UI.
    """
    source = (text or "").strip()
    if not enabled or not source:
        return source

    use_s1_syntax = model.casefold().startswith("s1")
    output: list[str] = []
    for match in _SENTENCE_RE.finditer(source):
        sentence = match.group(0)
        if _CUE_RE.match(sentence):
            output.append(sentence)
            continue
        leading = sentence[: len(sentence) - len(sentence.lstrip())]
        body = sentence.lstrip()
        cue = _cue_for_sentence(body)
        if cue and use_s1_syntax:
            cue = f"({cue[1:-1]})"
        output.append(f"{leading}{cue} {body}" if cue else sentence)

    # Keep unusual text that the conservative sentence regex did not split.
    decorated = "".join(output)
    return decorated or source
