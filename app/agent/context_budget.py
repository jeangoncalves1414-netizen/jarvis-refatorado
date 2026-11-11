"""Limites locais de contexto; não modifica o histórico ou as memórias salvas."""
from __future__ import annotations


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
