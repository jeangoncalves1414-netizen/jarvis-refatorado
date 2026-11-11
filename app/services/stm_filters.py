"""STM Filters (Semantic Transformation Modules) - Inspirado no G0DM0D3.

Filtra e normaliza as saídas geradas pelos LLMs para remover prolixidades,
preâmbulos robóticos e saudações repetitivas antes de exibir ao usuário.
"""
from __future__ import annotations

import re


_ROBOTIC_PREAMBLES = [
    r"^com certeza[!.,]?\s*(aqui está|segue abaixo|conforme solicitado)?[:\s]*",
    r"^com prazer[!.,]?\s*(aqui está|segue|vou te ajudar)?[:\s]*",
    r"^claro[!.,]?\s*(aqui está|vou|posso te ajudar com isso)?[:\s]*",
    r"^como um modelo de linguagem (de ia|ia|treinado)?\s*,?\s*",
    r"^como um assistente de ia\s*,?\s*",
    r"^como uma inteligência artificial\s*,?\s*",
    r"^olá[!.,]?\s*(como posso te ajudar hoje\??|em que posso ser útil\??)?\s*",
    r"^certamente[!.,]?\s*",
    r"^entendido[!.,]?\s*(aqui está|vou|posso)?[:\s]*",
    r"^(aqui estão|aqui está)?\s*(os\s+)?resultados?\s+(das?\s+)?ferramentas?[:\s]*",
    r"^resultados?\s+(da\s+)?pesquisa[:\s]*",
    r"^executando\s+(a\s+)?ferramenta[:\s]*",
    r"^vou\s+(pesquisar|buscar|verificar|analisar|abrir|executar)\b.*?[.:\n]+",
]


class STMFilterEngine:
    """Motor de polimento semântico de respostas de LLM."""

    def __init__(self) -> None:
        self.preamble_patterns = [re.compile(p, re.IGNORECASE) for p in _ROBOTIC_PREAMBLES]

    def clean_text(self, text: str) -> str:
        """Limpa o texto do LLM removendo enrolações robóticas no início."""
        if not text or not text.strip():
            return text

        result = text.strip()

        # Aplica a limpeza de preâmbulo robótico no início da primeira linha
        for pattern in self.preamble_patterns:
            result = pattern.sub("", result).lstrip()

        # Remove cabeçalhos técnicos soltos e despejos de links brutos gerados por modelos
        result = re.sub(r"(?im)^\s*(?:aqui\s+(?:est[aá]|est[aã]o)\s+)?(?:os\s+)?resultados?\s+(?:das?\s+)?(?:ferramentas?|a[cç][oõ]es)[:\s]*\n?", "", result)
        result = re.sub(r"(?im)^\s*resultados?\s+(?:da\s+)?(?:pesquisa|busca)[:\s]*\n?", "", result)

        # Remove linhas iniciais vazias geradas por cortes
        lines = result.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)

        return "\n".join(lines).strip()

    def filter_hesitations(self, text: str) -> str:
        """Preserva qualificadores de incerteza na resposta."""
        if not text:
            return text

        # Incerteza faz parte do significado; removê-la converte hipótese em afirmação.
        return text

    def process(self, text: str) -> str:
        """Aplica todas as transformações STM em sequência."""
        text = self.clean_text(text)
        text = self.filter_hesitations(text)
        return text

    def avoid_unsolicited_tables(self, text: str, request: str) -> str:
        """Keep chat readable when a prior answer makes the model imitate tables."""
        if re.search(r"\b(?:tabela|table|tabular|colunas?)\b", request or "", re.I):
            return text
        lines = text.splitlines()
        result: list[str] = []
        index = 0
        while index < len(lines):
            if (index + 1 < len(lines) and lines[index].strip().startswith("|")
                    and re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*", lines[index + 1])):
                headers = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                index += 2
                items: list[str] = []
                while index < len(lines) and lines[index].strip().startswith("|"):
                    cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                    parts = [f"{headers[pos]}: {value}" for pos, value in enumerate(cells) if value and pos < len(headers)]
                    if parts:
                        items.append("- " + "; ".join(parts))
                    index += 1
                result.extend(items)
                continue
            result.append(lines[index])
            index += 1
        return "\n".join(result).strip()


# Instância global do filtro STM
stm_filter = STMFilterEngine()
