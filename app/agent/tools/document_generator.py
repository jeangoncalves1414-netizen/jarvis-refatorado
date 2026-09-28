from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from .base import BaseTool, ToolResult

DEFAULT_EXPORT_DIR = Path("data/exports")


class DocumentGeneratorTool(BaseTool):
    """
    Gerador de Documentos — Cria relatórios e apresentações em formatos .pptx, .xlsx e .pdf
    diretamente a partir de texto estruturado ou dados fornecidos.
    """

    @property
    def name(self) -> str:
        return "document_generator"

    @property
    def description(self) -> str:
        return "Gera arquivos de documentos profissionais nos formatos .pptx (apresentação), .xlsx (planilha) ou .pdf a partir de texto ou dados estruturados."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["pptx", "xlsx", "pdf"],
                    "description": "Formato do documento a gerar.",
                },
                "title": {
                    "type": "string",
                    "description": "Título do documento.",
                },
                "content": {
                    "type": "string",
                    "description": "Conteúdo do documento (texto, linhas separadas por \\n para planilhas, slides separados por --- para PPTX).",
                },
                "output_path": {
                    "type": "string",
                    "description": "Caminho completo onde salvar o arquivo (opcional). Se omitido, salva em data/exports/.",
                },
            },
            "required": ["format", "title", "content"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        fmt = str(args.get("format", "pdf")).lower()
        title = str(args.get("title", "Documento Jarvis")).strip()
        content = str(args.get("content", "")).strip()
        output_path_str = args.get("output_path", "")

        DEFAULT_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:50]
        if output_path_str:
            output_file = Path(output_path_str)
        else:
            output_file = DEFAULT_EXPORT_DIR / f"{safe_title}.{fmt}"

        try:
            if fmt == "pptx":
                return self._generate_pptx(title, content, output_file)
            elif fmt == "xlsx":
                return self._generate_xlsx(title, content, output_file)
            elif fmt == "pdf":
                return self._generate_pdf(title, content, output_file)
            else:
                return ToolResult(ok=False, message=f"Formato '{fmt}' não suportado.")
        except Exception as e:
            return ToolResult(ok=False, message=f"Erro ao gerar documento: {e}")

    def _generate_pptx(self, title: str, content: str, output_file: Path) -> ToolResult:
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
        except ImportError:
            return ToolResult(ok=False, message="Biblioteca 'python-pptx' não instalada. Execute: pip install python-pptx")

        prs = Presentation()
        # Slide de título
        slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title
        if len(slide.placeholders) > 1:
            slide.placeholders[1].text = "Gerado por Jarvis"

        # Slides de conteúdo separados por ---
        slides_raw = content.split("---")
        for i, slide_text in enumerate(slides_raw):
            slide_text = slide_text.strip()
            if not slide_text:
                continue
            lines = slide_text.split("\n")
            slide_layout = prs.slide_layouts[1]
            new_slide = prs.slides.add_slide(slide_layout)
            new_slide.shapes.title.text = lines[0] if lines else f"Slide {i+1}"
            if len(new_slide.placeholders) > 1:
                new_slide.placeholders[1].text = "\n".join(lines[1:])

        prs.save(str(output_file))
        return ToolResult(ok=True, message=f"Apresentação PPTX criada com sucesso: {output_file}", data={"path": str(output_file)})

    def _generate_xlsx(self, title: str, content: str, output_file: Path) -> ToolResult:
        try:
            import openpyxl
            from openpyxl.styles import Font
        except ImportError:
            return ToolResult(ok=False, message="Biblioteca 'openpyxl' não instalada. Execute: pip install openpyxl")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = title[:31]

        # Título em negrito na linha 1
        ws["A1"] = title
        ws["A1"].font = Font(bold=True, size=14)

        # Cada linha de content = uma linha na planilha
        rows = content.split("\n")
        for row_idx, row_text in enumerate(rows, start=2):
            cells = row_text.split("\t") if "\t" in row_text else row_text.split(",")
            for col_idx, cell_val in enumerate(cells, start=1):
                ws.cell(row=row_idx, column=col_idx, value=cell_val.strip())

        wb.save(str(output_file))
        return ToolResult(ok=True, message=f"Planilha XLSX criada com sucesso: {output_file}", data={"path": str(output_file)})

    def _generate_pdf(self, title: str, content: str, output_file: Path) -> ToolResult:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
        except ImportError:
            return ToolResult(ok=False, message="Biblioteca 'reportlab' não instalada. Execute: pip install reportlab")

        doc = SimpleDocTemplate(str(output_file), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph(title, styles["Title"]))
        story.append(Spacer(1, 20))

        for line in content.split("\n"):
            story.append(Paragraph(line or " ", styles["Normal"]))
            story.append(Spacer(1, 4))

        doc.build(story)
        return ToolResult(ok=True, message=f"PDF gerado com sucesso: {output_file}", data={"path": str(output_file)})
