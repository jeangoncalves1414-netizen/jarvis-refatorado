"""Ferramenta de agente para análise e compreensão multimodal de vídeos locais e YouTube."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.core.actions import ToolMetadata
from app.services.video_intelligence import get_video_intelligence_service, VideoIntelligenceService


class VideoAnalystTool(BaseTool):
    """Ferramenta multimodal para análise inteligente de vídeos locais e do YouTube.
    
    Permite:
    1. 'analyze_local_video': Interpreta vídeos locais gravados em disco usando a Files API do Gemini 2.5 Flash.
    2. 'analyze_youtube_video': Analisa vídeos do YouTube a partir de transcrições com timestamps exatos [MM:SS].
    3. 'find_moments': Localiza momentos específicos de um tema ou palavra-chave com marcações temporais.
    """

    def __init__(self, service: VideoIntelligenceService | None = None) -> None:
        self._service = service

    @property
    def name(self) -> str:
        return "video_analyst"

    @property
    def description(self) -> str:
        return (
            "Análise e compreensão multimodal de vídeos locais e do YouTube. "
            "Use para interpretar gravações no computador (mp4, mkv, etc. via Gemini Files API), "
            "resumir ou tirar dúvidas sobre vídeos do YouTube citando marcações de tempo [MM:SS], "
            "ou encontrar o momento exato em que determinado assunto foi mencionado no vídeo."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "analyze_local_video",
                        "analyze_youtube_video",
                        "find_moments",
                    ],
                    "description": (
                        "Ação a executar: "
                        "'analyze_local_video' (processa arquivo local de vídeo via Gemini multimodal), "
                        "'analyze_youtube_video' (analisa transcrição com timestamps [MM:SS] de vídeo do YouTube), "
                        "'find_moments' (localiza trechos e timestamps específicos de um tópico ou termo no vídeo)."
                    ),
                },
                "file_path": {
                    "type": "string",
                    "description": "Caminho absoluto ou relativo para o arquivo de vídeo no disco local.",
                },
                "url": {
                    "type": "string",
                    "description": "URL do vídeo no YouTube (ou ID de 11 caracteres).",
                },
                "prompt": {
                    "type": "string",
                    "description": "Pergunta, instrução ou descrição do que você quer analisar no vídeo.",
                },
                "query": {
                    "type": "string",
                    "description": "Tópico, termo ou momento específico a buscar no vídeo para find_moments.",
                },
            },
            "required": ["action"],
        }

    @property
    def metadata(self) -> ToolMetadata:
        from .catalog import metadata_for

        fallback = ToolMetadata(
            capabilities=("video", "multimodal", "analysis"),
            default_risk="observe",
            operation_arguments=("action",),
            default_operation="analyze_youtube_video",
            operation_risks=(
                ("analyze_local_video", "observe"),
                ("analyze_youtube_video", "observe"),
                ("find_moments", "observe"),
            ),
            target_arguments=("url", "file_path", "query"),
            default_target="vídeo",
            operation_effects=(
                ("analyze_local_video", "Analisa o vídeo local via Gemini 2.5 Flash Multimodal; nenhum arquivo é alterado."),
                ("analyze_youtube_video", "Analisa transcrição temporizada de vídeo do YouTube com timestamps; nada é alterado."),
                ("find_moments", "Localiza trechos temporais específicos no vídeo correspondentes à busca; nada é alterado."),
            ),
            operation_reversibility=(
                ("analyze_local_video", "Nada a desfazer: operação de leitura e inferência multimodal."),
                ("analyze_youtube_video", "Nada a desfazer: operação de leitura de transcrição."),
                ("find_moments", "Nada a desfazer: operação de busca e leitura."),
            ),
            scope="Vídeo especificado local ou remotamente no YouTube.",
        )
        return metadata_for(self.name, fallback)

    def _get_service(self, context: dict[str, Any] | None = None) -> VideoIntelligenceService:
        if self._service is not None:
            return self._service
        settings = context.get("settings") if context else None
        return get_video_intelligence_service(settings=settings)

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execução direta para suporte ao protocolo BaseTool."""
        action = str(kwargs.get("action") or "").strip().lower()
        service = self._get_service()

        if action == "analyze_local_video":
            file_path = str(kwargs.get("file_path") or kwargs.get("url") or "").strip()
            prompt = str(kwargs.get("prompt") or kwargs.get("query") or "").strip()
            try:
                res = service.analyze_local_video(file_path=file_path, prompt=prompt)
                return {"ok": True, "analysis": res, "file_path": file_path, "message": res}
            except Exception as e:
                return {"ok": False, "error": str(e), "message": f"Erro na análise do vídeo local: {e}"}

        if action == "analyze_youtube_video":
            url = str(kwargs.get("url") or kwargs.get("file_path") or "").strip()
            prompt = str(kwargs.get("prompt") or kwargs.get("query") or "").strip()
            return service.analyze_youtube_video(url_or_id=url, question=prompt)

        if action == "find_moments":
            source = str(kwargs.get("url") or kwargs.get("file_path") or "").strip()
            query = str(kwargs.get("query") or kwargs.get("prompt") or "").strip()
            return service.find_moments(video_source=source, query=query)

        return {
            "ok": False,
            "error": f"Ação desconhecida '{action}'. Use analyze_local_video, analyze_youtube_video ou find_moments.",
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        args = args or {}
        action = str(args.get("action") or "").strip().lower()
        if not action:
            return ToolResult(ok=False, message="Parâmetro 'action' é obrigatório para video_analyst.")

        service = self._get_service(context)
        try:
            if action == "analyze_local_video":
                file_path = str(args.get("file_path") or args.get("url") or "").strip()
                if not file_path:
                    return ToolResult(ok=False, message="Caminho do arquivo ('file_path') é obrigatório para analyze_local_video.")
                prompt = str(args.get("prompt") or args.get("query") or "").strip()
                text = service.analyze_local_video(file_path=file_path, prompt=prompt)
                return ToolResult(ok=True, message=text, data={"analysis": text, "file_path": file_path})

            elif action == "analyze_youtube_video":
                url = str(args.get("url") or args.get("file_path") or "").strip()
                if not url:
                    return ToolResult(ok=False, message="URL ou ID do YouTube ('url') é obrigatório para analyze_youtube_video.")
                prompt = str(args.get("prompt") or args.get("query") or "").strip()
                res = service.analyze_youtube_video(url_or_id=url, question=prompt)
                ok = res.get("ok", False)
                msg = res.get("message") or res.get("analysis") or res.get("error", "Análise concluída.")
                return ToolResult(ok=ok, message=msg, data=res)

            elif action == "find_moments":
                source = str(args.get("url") or args.get("file_path") or "").strip()
                query = str(args.get("query") or args.get("prompt") or "").strip()
                if not source:
                    return ToolResult(ok=False, message="Fonte do vídeo ('url' ou 'file_path') é obrigatória para find_moments.")
                if not query:
                    return ToolResult(ok=False, message="Termo de pesquisa ('query') é obrigatório para find_moments.")
                res = service.find_moments(video_source=source, query=query)
                ok = res.get("ok", False)
                msg = res.get("message") or res.get("analysis") or res.get("error", "Busca de momentos concluída.")
                return ToolResult(ok=ok, message=msg, data=res)

            else:
                return ToolResult(
                    ok=False,
                    message=f"Ação '{action}' desconhecida para video_analyst. Use analyze_local_video, analyze_youtube_video ou find_moments.",
                )
        except Exception as exc:
            return ToolResult(ok=False, message=f"Erro ao executar video_analyst ({action}): {exc}")
