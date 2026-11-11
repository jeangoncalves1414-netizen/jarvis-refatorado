"""Decide, só por regra (zero chamada ao modelo), quando um pedido usa o loop agêntico."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# Radicais dos verbos de ação; casam formas conjugadas ("adiciona", "adicionei", "criar", "marque").
_ACTION_STEMS = (
    "adicion", "cri", "coloc", "marc", "marqu", "registr", "lanc", "anot", "agend", "abr", "abre",
    "apag", "remov", "mud", "atualiz", "mand", "envi", "pesquis", "procur", "lig", "deslig",
    "toc", "bebi", "gastei", "comprei", "exclu", "conclu", "complet", "corrij", "corrig", "cancel",
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
_LOOP_MODES = frozenset({"general", "chat", "lifeos"})


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().split())


_CLAUSE_SPLIT = re.compile(r"[,;!?]|\.(?=\s|$)|\b(?:e|depois|entao|em seguida|por fim|tambem|ai)\b")
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
        clause = re.sub(r"^\s*(?:(?:ta|ok|ola|certo)\s+)*(?:eu\s+)?quero\s+(?:que\s+voce\s+)?", "", clause)
        clause = re.sub(r"^\s*ao mesmo tempo\s+", "", clause)
        clause = re.sub(r"^\s*(?:de\s+)?(?:aguardar|esperar)\s+\d+\s+(?:segundos?|minutos?)\s+(?:eu\s+)?quero\s+(?:que\s+voce\s+)?", "", clause)
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


def is_action_request(text: str) -> bool:
    """Pedido imperativo; perguntas e discussão de ações não exigem execução."""
    normalized = normalize(text)
    words = re.findall(r"[a-z0-9]+", normalized)
    return not _is_conversation(normalized, words) and _action_verbs(normalized) > 0


def requires_tool_action(text: str) -> bool:
    if re.search(r'\b(?:desfaz\w*|estorn\w*|treinei|dormi|bebi|gastei|recebi)\b|na verdade foram|foi no cartao', normalize(text)):
        return True
    return is_action_request(text) and bool(re.search(
        r"\b(?:spotify|youtube|navegador|chrome|app|aplicativo|arquivo|pasta|janela|site|url|link|"
        r"habito\w*|tarefa\w*|agenda\w*|lembrete\w*|checklist\w*|despesa\w*|receita\w*|lancamento\w*|financ\w*|lista\w*|nota\w*|rotina\w*|pesquis\w*|documentacao|agua|volume|brilho|whatsapp)\b|https?://",
        normalize(text),
    ))


def is_action_discussion(text: str) -> bool:
    """A retrospective question is not permission to repeat a previous command."""
    value = normalize(text)
    return _action_verbs(value) == 0 and bool(re.search(
        r"\b(?:por que|porque|o que esta acontecendo)\b.*\bvoce\b.*\b(?:abrindo|abriu|fez|executou|repetindo|repetiu)\b|"
        r"\b(?:quais foram|o que)\b.*\bvoce\b.*\b(?:fez|executou|abriu)\b", value))


def missing_requested_steps(text: str, steps: list[dict[str, Any]]) -> list[str]:
    """Check explicit media openings and waits against ordered tool receipts.

    shortcut: other domains still rely on their tool/effect validators; extend when
    they expose structured completion requirements rather than guessing from prose.
    """
    from urllib.parse import urlparse
    normalized = normalize(text)
    if not is_action_request(text):
        return []
    required: list[tuple[int, str, int]] = []
    for match in re.finditer(r"\b(?:abr\w*|toc\w*|reproduz\w*|inici\w*)\b[^,;!?]{0,120}?\b((?:[a-z0-9-]+\.)+[a-z]{2,}|spotify|youtube|roblox|google)\b", normalized):
        target = match.group(1).removeprefix("www.")
        target = {site + '.com': site for site in ('spotify', 'youtube', 'roblox', 'google')}.get(target, target)
        required.append((match.start(), target, 0))
    if not mentions_alarm(text):
        previous_wait = None
        for match in _WAIT.finditer(normalized):
            seconds = wait_intent(match.group(0))
            if seconds and seconds <= 3600:
                # “aguarde 10 s e depois de 10 s feche” refers to the same pause.
                reference = match.group(0).startswith(("depois de", "apos"))
                gap = normalized[previous_wait.end():match.start()] if previous_wait else ""
                if previous_wait and reference and seconds == wait_intent(previous_wait.group(0)) and re.fullmatch(r"[\s,;]*(?:e\s*)?", gap):
                    continue
                required.append((match.start(), "wait", seconds))
                previous_wait = match
    missing, cursor = [], 0
    domains = {"tarefa": "task_tool", "habito": "habit_tool", "checklist": "checklist_tool",
               "lancamento": "finance_tool", "despesa": "finance_tool", "receita": "finance_tool"}
    for clause in _CLAUSE_SPLIT.split(normalized):
        if re.search(r"\bnao\b", clause):
            continue
        domain = next((tool for noun, tool in domains.items() if re.search(r"\b" + noun + r"s?\b", clause)), None)
        if not domain:
            continue
        operation = None
        if re.search(r"\b(?:exclu\w*|apag\w*|remov\w*)\b", clause):
            operation, accepted = "excluir", {"delete", "delete_list"}
        elif re.search(r"\b(?:conclu\w*|complet\w*|marque\w*)\b", clause):
            operation, accepted = "concluir", {"complete", "done", "toggle", "check", "check_many", "toggle_item"}
        elif re.search(r"\b(?:crie|criar|adicione|adicionar)\b", clause):
            operation, accepted = "criar", {"create", "create_many", "create_list", "add", "add_many"}
        elif re.search(r"\b(?:corrij\w*|corrig\w*|altere\w*|atualiz\w*)\b", clause):
            operation, accepted = "alterar", {"update"}
        kinds = {'task_tool': 'task', 'habit_tool': 'habit', 'finance_tool': 'finance', 'checklist_tool': 'checklist'}
        if operation and not any((s.get("name") == domain or (s.get('name') == 'personal_records' and (s.get('args') or {}).get('kind') == kinds[domain])) and s.get("status") == "succeeded" and (s.get("args") or {}).get("action") in accepted | {'preview'} for s in steps):
            missing.append(f"{operation} ({domain})")
    unordered = "ao mesmo tempo" in normalized and not any(target == 'wait' for _, target, _ in required)
    used = set()
    for _, target, seconds in sorted(required):
        found = None
        for index in range(cursor, len(steps)):
            if index in used:
                continue
            step = steps[index]
            if step.get('status') != 'succeeded':
                continue
            name, args = step.get('name'), step.get('args') or {}
            if target == 'wait':
                duration = args.get('seconds')
                matches = name == 'wait' and isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration >= seconds
            else:
                action = args.get('action', '')
                url = str(args.get('url') or args.get('query') or '')
                host = (urlparse(url if '://' in url else 'https://' + url).hostname or '').lower()
                domain = target if '.' in target else target + '.com'
                destination_matches = host == domain or host.endswith('.' + domain) or (target == 'youtube' and host == 'youtu.be')
                matches = (
                    (name == 'spotify' and target == 'spotify' and action in {'open', 'search_play', 'play_pause', 'next'}) or
                    (name in {'browser', 'browser_tool'} and action == 'navigate' and destination_matches) or
                    (name == 'web_search' and action == 'open_url' and destination_matches) or
                    (name == 'open_windows_app' and action == 'open' and normalize(str(args.get('app_name') or args.get('app') or '')) == target)
                )
            if matches:
                found = index
                break
        if found is None:
            missing.append(f"esperar {seconds} segundos" if target == 'wait' else f"abrir {target}")
        else:
            used.add(found)
            if not unordered:
                cursor = found + 1
    return missing


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
