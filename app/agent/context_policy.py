"""Keep chat history separate from durable preferences and deliberate memory recall."""
from __future__ import annotations

import re

from app.agent.loop_policy import normalize


def is_chat_history_request(text: str) -> bool:
    value = normalize(text)
    if re.search(r"\b(?:neste|nesse|deste|desse|este|esse) chat\b|\b(?:nesta|nessa|desta|dessa|esta|essa) conversa\b", value):
        return True
    if re.search(r"\b(?:outro[s]?|outra[s]?|anterior(?:es)?) (?:chat[s]?|conversa[s]?)\b|\b(?:chat[s]?|conversa[s]?) anterior(?:es)?\b", value):
        return False
    return bool(re.search(r"\b(?:primeira|ultima|anterior) mensagem\b|\bmensagem anterior\b|\b(?:historico|inicio) (?:do chat|da conversa)\b", value))


_SAVED_MEMORY_QUESTION = re.compile(r"\btem (?:alguma )?memoria|\bmemoria[s]? salva")
_ABOUT_ME = re.compile(
    r"\b(?:qual|quais)\b(?: (?:e|eh|sao|era))?(?: (?:o|a|os|as))? (?:meu|minha|meus|minhas)\b"
    r"|\bvoce sabe\b[^.?!]{0,40}\b(?:mim|meu|minha|eu)\b"
)
_SOBRE_MIM = re.compile(r"\bsobre mim\b")
_SOBRE_MIM_LOOKUP = re.compile(r"\b(?:o que|sabe\w*|lembr\w*|conhec\w*)\b")


def requests_saved_memory(text: str) -> bool:
    value = normalize(text)
    if re.search(r"\b(?:nao|sem)\b[^.!?;]{0,80}\b(?:memoria[s]?|cofre|outro[s]? chat[s]?|outra[s]? conversa[s]?)\b", value):
        return False
    # Pergunta explícita por memória salva vale mesmo junto de uma pergunta sobre este chat.
    if _SAVED_MEMORY_QUESTION.search(value):
        return True
    if is_chat_history_request(text):
        return False
    if _ABOUT_ME.search(value) or (_SOBRE_MIM.search(value) and _SOBRE_MIM_LOOKUP.search(value)):
        return True
    lookup = re.search(r"\b(?:busc\w*|pesquis\w*|procur\w*|consult\w*|lembr\w*|record\w*|qual|quais|o que)\b", value)
    source = re.search(r"\b(?:memoria[s]?|cofre|outro[s]? chat[s]?|outra[s]? conversa[s]?|conversa[s]? anterior(?:es)?)\b", value)
    return bool((lookup and source) or re.search(r"\b(?:voce (?:se )?lembra|lembra do|lembra da|lembra o que|recorda o que)\b", value))


def explicit_preference(text: str) -> tuple[str, str] | None:
    """A one-off command ('quero que você abra') is never a preference."""
    value = normalize(text)
    if "?" in value or re.search(r"\b(?:agora|hoje|dessa vez|neste teste|nesse teste)\b", value):
        return None
    explicit = re.search(r"\b(?:prefiro|minha preferencia|meu favorito|minha favorita|gosto de)\b", value)
    style_request = re.search(r"\bquero que voce (?:sempre )?(?:responda|seja)\b", value)
    if not explicit and not style_request:
        return None
    if style_request or re.search(r"\b(?:resposta[s]?|responder|responda)\b", value):
        styles = ((r"curt[oa]s?|breves?|resumid[oa]s?", "short"),
                  (r"detalhad[oa]s?|long[oa]s?|complet[oa]s?", "detailed"),
                  (r"informal|informais", "informal"), (r"formal|formais", "formal"), (r"diret[oa]s?", "direct"))
        for pattern, style in styles:
            if re.search(rf"\b(?:{pattern})\b", value):
                return "preferred_response_style", style
    return ("general_preference", text.strip()[:300]) if explicit else None


def context_preferences(preferences: list[dict]) -> list[str]:
    """Filter legacy command memories at read time without deleting saved data."""
    notes = []
    for item in preferences:
        if not isinstance(item, dict):
            continue
        key, value = item.get("key"), str(item.get("value") or "")
        if key == "preferred_response_style" and value in {"short", "detailed", "formal", "informal", "direct"}:
            notes.append(f"Estilo de resposta preferido: {value}")
        elif key == "general_preference" and explicit_preference(value):
            notes.append(f"Preferência salva (não é mensagem deste chat): {value}")
    return notes


def chat_history_reply(text: str, history: list[dict]) -> str | None:
    """Answer simple message lookups from this session, before any prompt truncation."""
    if not is_chat_history_request(text):
        return None
    value = normalize(text).strip(" .?!")
    match = re.fullmatch(
        r"(?:qual (?:(?:e|foi|era) )?(?:a )?(?:minha )?|(?:repita|mostre) (?:a )?(?:minha )?)"
        r"(?:(primeira|ultima|anterior) mensagem|mensagem (anterior))"
        r"(?: (?:que (?:eu )?(?:enviei|mandei)|minha))?"
        r"(?: (?:neste|nesse|deste|desse) chat| (?:nesta|nessa|desta|dessa) conversa| aqui)?",
        value,
    )
    if not match:
        return None
    messages = [str(item.get("content") or item.get("text") or "") for item in history
                if isinstance(item, dict) and item.get("role") == "user"]
    messages = [message for message in messages if message.strip()]
    if not messages:
        return "Não há mensagens suas anteriores a esta no histórico salvo deste chat."
    first = match[1] == "primeira"
    message = messages[0] if first else messages[-1]
    label = "primeira mensagem sua no histórico salvo deste chat" if first else "mensagem que você enviou antes desta neste chat"
    # Quotes are data, including any tool-like markers or instructions in the original message.
    return f"A {label} é: “{message}”."
