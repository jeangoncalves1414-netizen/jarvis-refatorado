"""
Módulo de Auto-Routing e Classificação Inteligente de Modos para o Jarvis.

Detecta a intenção do usuário em linguagem natural e seleciona automaticamente
o modo ideal entre:
- thinking: raciocínio profundo, dilemas, matemática, física, trade-offs, premissas.
- research: busca na web, notícias, cotações, comparações de mercado.
- coder: engenharia de software, scripts, bugs, regex, APIs, terminal, compilação.
- lifeos: hábitos, hidratação, lista de compras, gastos/despesas, treinos, rotinas.
- general: conversas gerais e assistente cotidiano.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalize_text(text: str) -> str:
    """Remove acentos e converte para minúsculas para correspondência robusta."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_marks.lower().strip()


# Padrões Fortes (Gatilhos de Alta Confiança)
_THINKING_STRONG = [
    r"^/(think|planejar|pensar)\b",
    r"\b(pense profundamente|raciocine passo a passo|pense passo a passo|analise profundamente|raciocinio profundo)\b",
    r"\b(dilema etico|trade-?off|trade-?offs|paradoxo de|silogismo|falacia logica)\b",
    r"\b(decomposicao de premissas|analise de premissas|teoria dos jogos|cenarios contra-factuais)\b",
    r"\b(demonstre que|derive a funcao|calculo integral|equacao diferencial|fisica quantica|termodinamica)\b",
    r"\b(pros e contras aprofundados|analise comparativa profunda|qual a melhor decisao estrategica)\b",
]

_THINKING_KEYWORDS = [
    r"\b(raciocine|raciocinio|delibere|reflita|premissas?|deducao|inducao|axiomas?|teoremas?)\b",
    r"\b(estrategia|estrategico|tradeoff|dilemas?|paradoxos?|heuristica|analise logica)\b",
]

_RESEARCH_STRONG = [
    r"^/(pesquisa|research|busca|buscar)\b",
    r"\b(pesquise na web|pesquise na internet|procure na web|procure na internet|busque no google|pesquise no google)\b",
    r"\b(ultimas noticias|noticias de hoje|noticias recentes|acontecimentos recentes|o que aconteceu com)\b",
    r"\b(cotacao do|preco do dolar|valor do bitcoin|preco do btc|cotacao hoje|taxa selic hoje|inflacao atual)\b",
    r"\b(comparativo de precos|onde comprar mais barato|melhores produtos de 202\d|review do|analise de mercado)\b",
]

_RESEARCH_KEYWORDS = [
    r"\b(pesquise|pesquisar|cotacao|cotacoes|noticias|fontes externas|busca na web|links de fontes)\b",
]

_CODER_STRONG = [
    r"^/(code|coder|dev)\b",
    r"```[a-zA-Z0-9_-]*\n",  # Bloco de código
    r"\b(escreva um codigo|crie uma funcao|implemente uma classe|crie um script|refatore|refatorar|refatoracao)\b",
    r"\b(debug|debugar|corrija o erro|corrija este erro|conserte o bug|traceback|stack ?trace)\b",
    r"\b(syntaxerror|typeerror|attributeerror|nullpointerexception|keyerror|runtimeerror)\b",
    r"\b(expressao regular|regex para|endpoint fast?api|api rest|banco de dados sql|query sql)\b",
    r"\b(git commit|git push|pull request|docker-compose|dockerfile|pip install|npm install|npm run|pytest)\b",
]

_CODER_KEYWORDS = [
    r"\b(python|typescript|javascript|golang|rustlang|c\+\+|csharp|html|css|tailwind|fastapi|react|nodejs|sql)\b",
    r"\b(funcao|script|compilacao|compilar|backend|frontend|api|terminal|bash|powershell|algoritmo)\b",
]

_LIFEOS_STRONG = [
    r"^/(lifeos|habito|tarefa|treino|gasto)\b",
    r"\b(bebi|tomei|beber|tomar)\s+(?:(?:\d+(?:[.,]\d+)?\s*(?:ml|l|litros?|copos?|garrafas?)\s+)?(?:de\s+)?)?agua\b",
    r"\b(habito|habitos|cumpri meu habito|rastrear habito|habito de)\b",
    r"\b(lista de compras|lista do mercado|adicione na lista de compras|comprar no mercado)\b",
    r"\b(gastei r\$?|despesa de|anote o gasto|paguei r\$?|comprei por r\$?|minhas financas)\b",
    r"\b(meu treino|treino de hoje|ficha de treino|fui na academia|exercicios de hoje|supino|agachamento)\b",
    r"\b(minha rotina|rotina matinal|rotina noturna|crie uma tarefa|adicione uma tarefa|checklist de hoje)\b",
    r"\b(me lembre de|crie um lembrete|lembrete para|minhas tarefas|to-do list)\b",
]

_LIFEOS_KEYWORDS = [
    r"\b(habito|habitos|tarefas?|lembretes?|compras|gastos?|despesas?|treinos?|rotinas?|hidratacao)\b",
]


def resolve_active_mode(
    user_text: str,
    explicit_mode: str = "auto",
    history: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Resolve o modo ativo do agente.

    Se explicit_mode for diferente de "auto" e "general" (ex: "planning", "thinking",
    "research", "coder", "lifeos", "tutor", "react", "swarm"), respeita a escolha explícita.

    Caso contrário ("auto" ou "general"), infere inteligentemente através de análise
    léxica, sintática e heurística de alta precisão baseada na mensagem atual e histórico.
    """
    raw_mode = (explicit_mode or "").strip().lower()

    # Honra escolha explícita se não for genérico/automático
    if raw_mode and raw_mode not in {"auto", "general"}:
        return raw_mode, {
            "strategy": "explicit",
            "mode": raw_mode,
            "confidence": 1.0,
            "reason": f"Modo explícito '{raw_mode}' selecionado pelo usuário.",
        }

    text = user_text or ""
    normalized = _normalize_text(text)

    if not normalized:
        return "general", {
            "strategy": "fallback",
            "mode": "general",
            "confidence": 0.5,
            "reason": "Texto vazio ou sem conteúdo analisável.",
        }

    scores: dict[str, float] = {
        "thinking": 0.0,
        "research": 0.0,
        "coder": 0.0,
        "lifeos": 0.0,
    }
    matches: dict[str, list[str]] = {
        "thinking": [],
        "research": [],
        "coder": [],
        "lifeos": [],
    }

    # Avaliação por padrões fortes (peso 10.0)
    mode_patterns = [
        ("thinking", _THINKING_STRONG, 10.0),
        ("research", _RESEARCH_STRONG, 10.0),
        ("coder", _CODER_STRONG, 10.0),
        ("lifeos", _LIFEOS_STRONG, 10.0),
    ]

    for mode_name, patterns, weight in mode_patterns:
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE) or re.search(pat, normalized, re.IGNORECASE)
            if m:
                scores[mode_name] += weight
                matches[mode_name].append(m.group(0))

    # Avaliação por palavras-chave (peso 2.5)
    keyword_patterns = [
        ("thinking", _THINKING_KEYWORDS, 2.5),
        ("research", _RESEARCH_KEYWORDS, 2.5),
        ("coder", _CODER_KEYWORDS, 2.5),
        ("lifeos", _LIFEOS_KEYWORDS, 2.5),
    ]

    for mode_name, patterns, weight in keyword_patterns:
        for pat in patterns:
            found = re.findall(pat, normalized, re.IGNORECASE)
            if found:
                scores[mode_name] += weight * min(len(found), 3)
                matches[mode_name].extend(found[:3])

    # Se houver menção explícita de código ou blocos de código
    if "```" in text:
        scores["coder"] += 12.0
        matches["coder"].append("code_block")

    # Desambiguação de intenção composta:
    # Ex: "pesquise as últimas notícias do python" -> intenção primária é pesquisa, não coder
    if scores["research"] >= 10.0 and scores["coder"] < 10.0:
        scores["coder"] = max(0.0, scores["coder"] - 5.0)

    # Ex: "escreva um script python para pesquisar arquivos" -> intenção primária é coder
    if scores["coder"] >= 10.0 and scores["research"] < 10.0:
        scores["research"] = max(0.0, scores["research"] - 5.0)

    # Identificar vencedor com limite mínimo de relevância
    best_mode, max_score = max(scores.items(), key=lambda item: item[1])

    if max_score >= 4.0:
        confidence = min(0.98, 0.65 + (max_score / 30.0))
        resolved = best_mode
        reason = f"Detectado via padrões de {best_mode}: {', '.join(matches[best_mode][:3])}"
    else:
        resolved = "general"
        confidence = 0.6
        reason = "Nenhum modo especializado atingiu o limiar de confiança; fallback para conversa geral."

    metadata = {
        "strategy": "auto",
        "mode": resolved,
        "confidence": round(confidence, 2),
        "reason": reason,
        "scores": {k: round(v, 2) for k, v in scores.items()},
        "matches": matches[best_mode] if best_mode in matches else [],
    }

    return resolved, metadata
