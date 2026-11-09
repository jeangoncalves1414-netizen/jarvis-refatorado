"""Módulo de Inteligência Multimodal de Vídeo para o Jarvis.

Suporta:
1. Vídeos locais via Google Gemini Files API e modelo gemini-2.5-flash multimodal.
2. Vídeos do YouTube via YouTubeTranscriptApi com timestamps [MM:SS] e síntese inteligente via LLM.
3. Busca de momentos e tópicos específicos (find_moments).
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

logger = logging.getLogger(__name__)


def extract_youtube_id(url_or_id: str) -> str | None:
    """Extrai o ID de 11 caracteres de um vídeo do YouTube a partir de URL ou string direta."""
    if not url_or_id:
        return None
    cleaned = str(url_or_id).strip()
    if re.fullmatch(r"[\w-]{11}", cleaned):
        return cleaned

    patterns = [
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/|\/live\/)([a-zA-Z0-9_-]{11})",
        r"[?&]v=([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            return match.group(1)
    return None


def format_timestamp(seconds: float) -> str:
    """Converte segundos em marcação de tempo [MM:SS] ou [HH:MM:SS]."""
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes:02d}:{secs:02d}]"


class VideoIntelligenceService:
    """Serviço multimodal de inteligência e interpretação de vídeos."""

    def __init__(self, settings: Any = None) -> None:
        self.settings = settings

    def _resolve_settings(self, settings_override: Any = None) -> Any:
        if settings_override is not None:
            return settings_override
        if self.settings is not None:
            return self.settings
        try:
            from app.config import load_settings
            return load_settings()
        except Exception:
            return None

    def _resolve_gemini_api_key(self, settings: Any) -> str:
        key = getattr(settings, "gemini_api_key", "")
        if not key:
            keys = getattr(settings, "gemini_api_keys", [])
            if keys and keys[0]:
                key = keys[0]
        if not key:
            key = os.getenv("GEMINI_API_KEY", "")
        return str(key).strip()

    def analyze_local_video(
        self,
        file_path: str,
        prompt: str = "Descreva detalhadamente o que acontece neste vídeo, suas cenas principais e eventos relevantes.",
        settings: Any = None,
    ) -> str:
        """Analisa um arquivo de vídeo local fazendo upload temporário para a Gemini Files API."""
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo de vídeo não encontrado no caminho: {file_path}")

        current_settings = self._resolve_settings(settings)
        api_key = self._resolve_gemini_api_key(current_settings)
        if not api_key:
            raise ValueError(
                "Chave GEMINI_API_KEY não configurada. Defina a variável GEMINI_API_KEY no .env para analisar vídeos locais."
            )

        try:
            from google import genai
        except ImportError:
            raise RuntimeError("Biblioteca 'google.genai' não está instalada no ambiente.")

        client = genai.Client(api_key=api_key)
        video_file = None
        try:
            logger.info("Enviando vídeo '%s' para a API do Gemini Files...", file_path)
            video_file = client.files.upload(file=file_path)

            # Aguarda o processamento do arquivo de vídeo se estiver pendente
            poll_count = 0
            while hasattr(video_file, "state") and getattr(video_file.state, "name", "") == "PROCESSING":
                time.sleep(2)
                video_file = client.files.get(name=video_file.name)
                poll_count += 1
                if poll_count > 60:
                    raise TimeoutError("Tempo limite esgotado ao aguardar o processamento do vídeo no Gemini.")

            if hasattr(video_file, "state") and getattr(video_file.state, "name", "") == "FAILED":
                err = getattr(video_file, "error", None)
                msg = getattr(err, "message", "Erro desconhecido") if err else "Falha de codificação"
                raise RuntimeError(f"O Gemini não conseguiu processar este vídeo: {msg}")

            model_name = "gemini-2.5-flash"
            contents = [video_file, prompt or "Descreva o que acontece neste vídeo."]
            logger.info("Gerando análise multimodal com modelo %s...", model_name)
            response = client.models.generate_content(model=model_name, contents=contents)

            return getattr(response, "text", str(response)).strip()

        finally:
            if video_file and hasattr(video_file, "name"):
                try:
                    client.files.delete(name=video_file.name)
                    logger.info("Arquivo remoto %s removido com sucesso.", video_file.name)
                except Exception as del_err:
                    logger.warning("Falha ao remover arquivo temporário do Gemini Files: %s", del_err)

    def _fetch_transcript_snippets(self, video_id: str) -> list[dict[str, Any]]:
        """Busca os trechos da transcrição de um vídeo do YouTube via YouTubeTranscriptApi."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            raise RuntimeError("Biblioteca 'youtube_transcript_api' não está instalada.")

        languages = ["pt", "pt-BR", "en"]

        # Suporte a versões legadas (get_transcript estático)
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            try:
                return YouTubeTranscriptApi.get_transcript(video_id, languages=languages)  # type: ignore[no-any-return]
            except Exception:
                return YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[no-any-return]

        # Suporte à versão mais recente (instância com fetch ou list)
        api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(video_id, languages=languages)
        except Exception:
            try:
                tlist = api.list(video_id)
                try:
                    t = tlist.find_transcript(languages)
                except Exception:
                    t = next(iter(tlist))
                fetched = t.fetch()
            except Exception:
                fetched = api.fetch(video_id)

        if hasattr(fetched, "to_raw_data"):
            return fetched.to_raw_data()  # type: ignore[no-any-return]

        items: list[dict[str, Any]] = []
        for s in fetched:
            if isinstance(s, dict):
                items.append(s)
            else:
                items.append({
                    "text": getattr(s, "text", ""),
                    "start": getattr(s, "start", 0.0),
                    "duration": getattr(s, "duration", 0.0),
                })
        return items

    def analyze_youtube_video(
        self,
        url_or_id: str,
        question: str = "",
        settings: Any = None,
    ) -> dict[str, Any]:
        """Obtém a transcrição com timestamps do YouTube e gera resposta ou resumo citando os momentos [MM:SS]."""
        video_id = extract_youtube_id(url_or_id)
        if not video_id:
            return {
                "ok": False,
                "error": f"Não foi possível identificar o ID do vídeo a partir de '{url_or_id}'.",
                "message": "ID do vídeo do YouTube inválido.",
            }

        try:
            raw_snippets = self._fetch_transcript_snippets(video_id)
        except Exception as exc:
            return {
                "ok": False,
                "video_id": video_id,
                "error": f"Erro ao obter transcrição: {exc}",
                "message": f"Não foi possível obter a transcrição do vídeo {video_id}. Detalhes: {exc}",
            }

        if not raw_snippets:
            return {
                "ok": False,
                "video_id": video_id,
                "error": "A transcrição do vídeo retornou vazia.",
                "message": "Transcrição do vídeo vazia ou desativada.",
            }

        # Formata a transcrição com marcações de tempo [MM:SS]
        formatted_lines = []
        for snippet in raw_snippets:
            start_sec = snippet.get("start", 0.0)
            ts = format_timestamp(start_sec)
            txt = str(snippet.get("text", "")).strip()
            if txt:
                formatted_lines.append(f"{ts} {txt}")

        formatted_transcript = "\n".join(formatted_lines)
        # Limite de segurança de caracteres para prompt
        transcript_for_prompt = formatted_transcript[:25000]

        user_query = (
            question.strip()
            if question and question.strip()
            else "Faça um resumo completo dos principais pontos abordados no vídeo, destacando a evolução do assunto."
        )

        prompt = (
            "Você é o assistente analista de vídeos do Jarvis.\n"
            "Abaixo está a transcrição oficial temporizada de um vídeo do YouTube com marcações [MM:SS].\n"
            "Analise as informações e responda à pergunta ou elabore o resumo com alta clareza.\n\n"
            "REGRAS OBRIGATÓRIAS:\n"
            "1. Sempre que citar uma fala, tema ou explicação importante, indique EXATAMENTE o timestamp correspondente no formato [MM:SS].\n"
            "2. Não invente timestamps; use rigorosamente os marcadores presentes na transcrição.\n"
            "3. Estruture em tópicos objetivos quando apropriado.\n\n"
            f"PERGUNTA/OBJETIVO: {user_query}\n\n"
            "TRANSCRIÇÃO DO VÍDEO:\n"
            f"{transcript_for_prompt}"
        )

        current_settings = self._resolve_settings(settings)
        try:
            from app.services.llm import LLMService
            llm = LLMService(settings=current_settings)
            analysis_text = llm.ask(prompt)
        except Exception as llm_err:
            analysis_text = (
                f"Transcrição obtida com sucesso ({len(raw_snippets)} falas), mas houve erro ao chamar o modelo LLM: {llm_err}\n\n"
                f"Amostra da transcrição:\n{formatted_transcript[:1000]}"
            )

        return {
            "ok": True,
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "analysis": analysis_text,
            "total_snippets": len(raw_snippets),
            "transcript_preview": formatted_transcript[:1200] + ("..." if len(formatted_transcript) > 1200 else ""),
            "message": analysis_text,
        }

    def find_moments(
        self,
        video_source: str,
        query: str,
        settings: Any = None,
    ) -> dict[str, Any]:
        """Localiza momentos exatos com timestamps correspondentes ao assunto pesquisado."""
        if not query or not query.strip():
            return {
                "ok": False,
                "error": "Consulta (query) é obrigatória para buscar momentos no vídeo.",
                "message": "Parâmetro query não informado.",
            }

        # Verifica se é YouTube ou vídeo local
        yt_id = extract_youtube_id(video_source)
        if yt_id:
            instruction = (
                f"Localize todos os momentos e trechos onde o seguinte assunto é abordado: '{query}'. "
                "Para cada ocorrência, cite o timestamp [MM:SS], a fala correspondente e um breve resumo do contexto."
            )
            return self.analyze_youtube_video(url_or_id=yt_id, question=instruction, settings=settings)

        # Trata como vídeo local
        if os.path.exists(video_source):
            prompt = (
                f"Localize momentos específicos neste vídeo relacionados ao tema: '{query}'. "
                "Para cada momento identificado, indique o tempo aproximado em que acontece e o que pode ser visto ou ouvido."
            )
            try:
                analysis = self.analyze_local_video(file_path=video_source, prompt=prompt, settings=settings)
                return {
                    "ok": True,
                    "video_source": video_source,
                    "query": query,
                    "analysis": analysis,
                    "message": analysis,
                }
            except Exception as e:
                return {
                    "ok": False,
                    "video_source": video_source,
                    "query": query,
                    "error": str(e),
                    "message": f"Erro ao analisar momentos no vídeo local: {e}",
                }

        return {
            "ok": False,
            "error": f"Fonte de vídeo '{video_source}' não é uma URL válida do YouTube nem um arquivo local existente.",
            "message": "Fonte de vídeo inválida.",
        }


_VIDEO_SERVICE: VideoIntelligenceService | None = None


def get_video_intelligence_service(settings: Any = None) -> VideoIntelligenceService:
    """Retorna instância singleton do serviço de inteligência de vídeo."""
    global _VIDEO_SERVICE
    if _VIDEO_SERVICE is None or settings is not None:
        _VIDEO_SERVICE = VideoIntelligenceService(settings=settings)
    return _VIDEO_SERVICE
