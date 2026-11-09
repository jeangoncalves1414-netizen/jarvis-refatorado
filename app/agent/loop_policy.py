"""Decide, só por regra (zero chamada ao modelo), quando um pedido usa o loop agêntico."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# Radicais dos verbos de ação; casam formas conjugadas ("adiciona", "adicionei", "criar", "marque").
_ACTION_STEMS = (
    "adicion", "cri", "coloc", "marc", "registr", "lanc", "anot", "agend", "abr", "abre",
    "apag", "remov", "mud", "atualiz", "mand", "envi", "pesquis", "procur", "lig", "deslig",
    "toc", "bebi", "gastei", "comprei",
)
# Palavras que começam com os radicais curtos mas não são pedidos de ação.
_NOT_ACTIONS = frozenset({
    "criança", "crianca", "criancas", "criativo", "criativa", "criatividade", "cristal", "critica", "critico",
    "marca", "marcas", "abril", "abraco", "abrigo", "mudo", "ligeiro", "ligacao", "liga", "toca", "lancha",
    "lanche", "lanches", "mundo", "registro", "registros", "envio", "procura", "pesquisa", "anotacao", "anotacoes",
    "agenda", "remove", "mudanca", "mudancas",
})
_IMPERATIVE_NOUNS = frozenset({"agenda", "liga", "toca", "procura", "pesquisa", "remove", "marca"})
_SEQUENCE = ("depois", "em seguida", "e entao", "por fim", "tambem", ";")
_VERIFY = ("confere se", "verifica se", "confirma se", "confira se", "verifique se")
_EXCLUDED_MODES = frozenset({"tutor", "planning", "research", "swarm", "vision", "coder"})
_LOOP_MODES = frozenset({"general", "chat"})


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().split())


_CLAUSE_SPLIT = re.compile(r"[,;.]|\b(?:e|depois|entao|em seguida|por fim|tambem|ai)\b")
_LEADING_FILLERS = frozenset({"jarvis", "pode", "poderia", "agora", "entao", "tambem", "ai", "por", "favor", "me"})
# Conversa/pergunta: abre o pedido (depois dos preenchimentos) ou aparece em qualquer lugar do texto.
_CONVERSATION_STARTS = (
    "o que", "por que", "porque", "como", "explica", "explique", "qual", "quais", "quem", "onde", "quanto", "quantos",
    "voce acha", "voce acredita", "voce sabe",
)
_CONVERSATION_ANYWHERE = ("voce acha", "por que")


def _is_conversation(normalized: str, words: list[str]) -> bool:
    if "?" in normalized:
        return True
    padded = f" {normalized} "
    if any(f" {phrase} " in padded for phrase in _CONVERSATION_ANYWHERE):
        return True
    head = list(words)
    while head and head[0] in _LEADING_FILLERS:
        head.pop(0)
    start = " ".join(head)
    return any(start == phrase or start.startswith(phrase + " ") for phrase in _CONVERSATION_STARTS)


def _action_verbs(normalized: str) -> int:
    """Conta verbos de ação só no começo de cada oração ("adiciona ler, depois agenda dentista")."""
    count = 0
    for clause in _CLAUSE_SPLIT.split(normalized.replace("por favor", " ")):
        words = re.findall(r"[a-z0-9]+", clause)
        while words and words[0] in _LEADING_FILLERS:
            words.pop(0)
        if not words:
            continue
        word = words[0]
        if word in _NOT_ACTIONS:
            # "agenda dentista", "liga a luz": substantivo no início da oração é verbo no imperativo.
            count += word in _IMPERATIVE_NOUNS
        elif word in {"bebi", "gastei", "comprei"} or any(word.startswith(stem) for stem in _ACTION_STEMS if len(word) >= len(stem) + 1):
            count += 1
    return count


_WAIT = re.compile(
    r"\b(?:espera|espere|esperar|aguarda|aguarde|aguardar|depois de|apos)\s+(?:uns\s+|por\s+)?(\d+)\s*"
    r"(segundos?|seg|s|minutos?|min|m|horas?|h)\b"
)
_ALARM = re.compile(r"\balarme|\btimer\b|\btemporizador|\bme avis|\bme lembr|\bavise\b|\blembre\b|\bdespert")


def wait_intent(text: str) -> int | None:
    """Segundos da primeira espera pedida ("aguarde 50 segundos" -> 50); ``None`` sem espera."""
    match = _WAIT.search(normalize(text))
    if not match:
        return None
    unit = match.group(2)
    factor = 3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1
    return int(match.group(1)) * factor


def mentions_alarm(text: str) -> bool:
    """Pedido de aviso sonoro (alarme, timer, "me avisa", "me lembra"): ``timer`` continua no turno."""
    return bool(_ALARM.search(normalize(text)))


def should_use_agent_loop(text: str, mode: str, settings: dict[str, Any]) -> tuple[bool, str]:
    """Devolve (usar o loop?, motivo curto). ``settings`` vem de ``get_agent_loop_settings()``."""
    if mode == "react":
        return True, "modo execução por etapas"
    if mode in _EXCLUDED_MODES or mode not in _LOOP_MODES:
        return False, "modo sem loop"
    choice = str((settings or {}).get("mode") or "auto")
    if choice == "off":
        return False, "loop desligado"
    normalized = normalize(text)
    if not normalized:
        return False, "texto vazio"
    if choice == "always":
        return True, "loop sempre ligado"
    words = re.findall(r"[a-z0-9]+", normalized)
    if len(words) < 4:
        return False, "pedido curto"
    # Espera entre ações ("abre o Spotify, aguarde 50 s e abre o YouTube") só funciona no loop, em ordem.
    if "?" not in normalized and wait_intent(normalized) is not None and _action_verbs(normalized) >= 1:
        return True, "pedido com espera"
    if _is_conversation(normalized, words):
        return False, "pergunta ou conversa"
    verbs = _action_verbs(normalized)
    if any(phrase in normalized for phrase in _VERIFY) and verbs >= 1:
        return True, "pedido com verificação"
    if verbs >= 2:
        return True, "pedido com várias ações"
    if verbs >= 1 and any((f" {item} " in f" {normalized} ") if item != ";" else item in normalized for item in _SEQUENCE):
        return True, "pedido em sequência"
    return False, "pedido simples"