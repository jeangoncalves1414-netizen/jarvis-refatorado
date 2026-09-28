"""
AI Diagram Copilot — Gerador Inteligente de Diagramas Interativos (Mermaid.js)
Gera gráficos de fluxo, diagramas de sequência, mapas mentais e modelos de classe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class DiagramType(str, Enum):
    FLOWCHART = "graph TD"
    SEQUENCE = "sequenceDiagram"
    CLASS_DIAGRAM = "classDiagram"
    MINDMAP = "mindmap"
    ER_DIAGRAM = "erDiagram"


@dataclass
class DiagramResult:
    ok: bool
    diagram_type: str
    mermaid_code: str
    title: str = ""
    description: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "diagram_type": self.diagram_type,
            "mermaid_code": self.mermaid_code,
            "title": self.title,
            "description": self.description,
            "error": self.error,
        }


class DiagramCopilotService:
    """Serviço gerador e validador de diagramas Mermaid.js."""

    @staticmethod
    def generate_flowchart(title: str, steps: list[tuple[str, str, str]]) -> DiagramResult:
        """
        Gera um fluxograma (Flowchart TD) a partir de uma lista de conexões (origem, rótulo, destino).
        """
        lines = ["graph TD", "    classDef nodeStyle fill:#131313,stroke:#00daf8,stroke-width:2px,color:#fff;"]
        nodes_seen = set()

        for src, label, dst in steps:
            src_clean = re.sub(r"\W+", "_", src)
            dst_clean = re.sub(r"\W+", "_", dst)
            if src_clean not in nodes_seen:
                lines.append(f'    {src_clean}["{src}"]:::nodeStyle')
                nodes_seen.add(src_clean)
            if dst_clean not in nodes_seen:
                lines.append(f'    {dst_clean}["{dst}"]:::nodeStyle')
                nodes_seen.add(dst_clean)
            if label:
                lines.append(f'    {src_clean} -->|"{label}"| {dst_clean}')
            else:
                lines.append(f'    {src_clean} --> {dst_clean}')

        code = "\n".join(lines)
        return DiagramResult(ok=True, diagram_type="flowchart", mermaid_code=code, title=title)

    @staticmethod
    def generate_sequence(title: str, interactions: list[tuple[str, str, str]]) -> DiagramResult:
        """
        Gera um diagrama de sequência (sequenceDiagram) a partir de (origem, mensagem, destino).
        """
        lines = ["sequenceDiagram", "    autonumber"]
        participants = set()

        for src, msg, dst in interactions:
            participants.add(src)
            participants.add(dst)

        for p in sorted(participants):
            p_clean = re.sub(r"\W+", "_", p)
            lines.append(f'    participant {p_clean} as {p}')

        for src, msg, dst in interactions:
            src_clean = re.sub(r"\W+", "_", src)
            dst_clean = re.sub(r"\W+", "_", dst)
            lines.append(f'    {src_clean}->>{dst_clean}: {msg}')

        code = "\n".join(lines)
        return DiagramResult(ok=True, diagram_type="sequence", mermaid_code=code, title=title)

    @staticmethod
    def sanitize_mermaid(code: str) -> str:
        """Limpa blocos markdown ```mermaid ... ``` se presentes."""
        code = code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            code = "\n".join(lines).strip()
        return code

    @classmethod
    def from_text_prompt(cls, prompt: str, mermaid_response: str) -> DiagramResult:
        """Processa a resposta em texto do LLM e extrai o diagrama Mermaid válido."""
        clean_code = cls.sanitize_mermaid(mermaid_response)
        first_line = clean_code.split("\n")[0].strip() if clean_code else ""

        dtype = "unknown"
        if "graph " in first_line or "flowchart " in first_line:
            dtype = "flowchart"
        elif "sequenceDiagram" in first_line:
            dtype = "sequence"
        elif "classDiagram" in first_line:
            dtype = "class"
        elif "mindmap" in first_line:
            dtype = "mindmap"
        elif "erDiagram" in first_line:
            dtype = "er"

        return DiagramResult(
            ok=bool(clean_code),
            diagram_type=dtype,
            mermaid_code=clean_code,
            title=f"Diagrama ({dtype.capitalize()})",
            description=prompt[:150],
        )
