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


def _action_verbs(words: list[str]) -> int:
    count = 0
    for index, word in enumerate(words):
        if word in _NOT_ACTIONS:
            # "agenda dentista", "liga a luz": substantivo no início da frase ou depois de vírgula/conector é verbo.
            if word in _IMPERATIVE_NOUNS and (index == 0 or words[index - 1] in {"e", "depois", "entao", "tambem", ","}):
                count += 1
            continue
        if word in {"bebi", "gastei", "comprei"} or any(word.startswith(stem) for stem in _ACTION_STEMS if len(word) >= len(stem) + 1):
            count += 1
    return count


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
    tokens = re.findall(r"[a-z0-9]+|[,;]", normalized)
    words = [token for token in tokens if token not in {",", ";"}]
    if len(words) < 4:
        return False, "pedido curto"
    verbs = _action_verbs(tokens)
    if any(phrase in normalized for phrase in _VERIFY) and verbs >= 1:
        return True, "pedido com verificação"
    if normalized.endswith("?") and verbs == 0:
        return False, "pergunta"
    if verbs >= 2:
        return True, "pedido com várias ações"
    if verbs >= 1 and any((f" {item} " in f" {normalized} ") if item != ";" else item in normalized for item in _SEQUENCE):
        return True, "pedido em sequência"
    return False, "pedido simples"
