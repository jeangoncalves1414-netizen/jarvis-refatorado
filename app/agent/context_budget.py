"""Limites locais de contexto; não modifica o histórico ou as memórias salvas."""
from __future__ import annotations

import copy
import json
import math
import re

REQUEST_BUDGET = 6000
FALLBACK_ABOVE = 7000


def record_context_usage(before: int, after: int, *, provider: str, model: str,
                         budget: int | None = None) -> None:
    """Numeric estimates only; never retain prompts in turn metadata."""
    from app.agent import turn_meta
    turn_meta.append("context_usage", {
        "provider": provider, "model": model, "estimated_tokens": after,
        "before_tokens": before, "budget": budget,
        "reduced": after < before,
    }, limit=32)


def estimate_tokens(messages: list[dict], tools: list[dict] | None = None) -> int:
    return math.ceil(len(json.dumps({"messages": messages, "tools": tools or []}, ensure_ascii=False)) / 3.2)


def fit_request(messages: list[dict], tools: list[dict] | None = None,
                budget: int = REQUEST_BUDGET) -> tuple[list[dict], list[dict]]:
    """Trim optional tools, old turns, then situational context; preserve rules and latest request.

    An irreducible request can exceed budget: callers must fall back or stop, never send it.
    """
    rows, selected = copy.deepcopy(messages), copy.deepcopy(tools or [])
    last_user = next((i for i in range(len(rows) - 1, -1, -1) if rows[i].get("role") == "user"), -1)
    text = str(rows[last_user].get("content") or "") if last_user >= 0 else ""
    from app.agent.tools.registry import GROQ_KEYWORD_TOOLS, LOOP_KEYWORD_TOOLS
    from app.agent.loop_policy import normalize
    normalized = normalize(text)
    mentioned = {name for pattern, names in GROQ_KEYWORD_TOOLS + LOOP_KEYWORD_TOOLS
                 if pattern.search(normalized) for name in names}
    for tool in sorted(selected[:], key=lambda t: len(json.dumps(t)), reverse=True):
        name = (tool.get("function") or tool).get("name", "")
        if estimate_tokens(rows, selected) <= budget:
            break
        if name not in mentioned and name not in text:
            selected.remove(tool)
    # Remove complete old turns; never leave orphaned tool responses.
    while estimate_tokens(rows, selected) > budget:
        users = [i for i, row in enumerate(rows) if row.get("role") == "user"]
        if len(users) < 2:
            break
        del rows[users[0]:users[1]]
    if estimate_tokens(rows, selected) > budget:
        for row in rows:
            if row.get("role") == "system":
                row["content"] = re.sub(r"(?m)^## Situação agora\n.*?(?=^## |\Z)", "",
                                        str(row.get("content") or ""), flags=re.S)
    return rows, selected


def memory_notes(notes: list[str], budget: int = 2400) -> str:
    lines, seen = [], set()
    for note in notes:
        text = str(note).strip()
        key = " ".join(text.casefold().split())
        if not text or key in seen:
            continue
        seen.add(key)
        line = "- " + text[:400]
        if len(line) + 1 > budget:
            break
        lines.append(line)
        budget -= len(line) + 1
    return "\n".join(lines) or "(Sem ajustes na memória)"


def conversation_messages(history: list[dict], budget: int = 16000) -> list[dict]:
    """Só role/content; mensagens mais recentes têm prioridade. Não inclui metadados de UI."""
    kept = []
    for item in reversed(history):
        if item.get("role") not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "")
        if not content:
            continue
        if len(content) > budget:
            # Não cortar a mensagem mais recente: pode conter código ou restrições essenciais.
            if not kept:
                kept.append({"role": item["role"], "content": content})
            break
        kept.append({"role": item["role"], "content": content})
        budget -= len(content)
    return list(reversed(kept))
