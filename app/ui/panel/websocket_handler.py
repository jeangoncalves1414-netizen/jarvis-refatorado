"""WebSocket handler para streaming de voz em tempo real."""
from __future__ import annotations

import asyncio
import json
import base64
from typing import Any
from websockets.server import WebSocketServerProtocol


class VoiceWebSocketHandler:
    """Handler para WebSocket de voz em tempo real."""
    
    def __init__(self, websocket: WebSocketServerProtocol, settings: Any):
        self.ws = websocket
        self.settings = settings
        self.running = False
        self.audio_buffer = []
        self.buffer_size = 0
        self.max_buffer_size = 32768  # 32KB
        
    async def handle(self):
        """Loop principal do WebSocket."""
        self.running = True
        try:
            await self.ws.send(json.dumps({
                "type": "connected",
                "message": "WebSocket conectado para streaming de voz"
            }))
            
            # Processar mensagens do cliente
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                except json.JSONDecodeError:
                    # Mensagem binária (áudio)
                    await self._process_audio_chunk(message)
                    
        except Exception as e:
            print(f"[VoiceWS] Erro: {e}")
        finally:
            self.running = False
            
    async def _process_message(self, data: dict):
        """Processa mensagens de controle."""
        msg_type = data.get("type")
        
        if msg_type == "start":
            await self._start_session()
        elif msg_type == "stop":
            await self._stop_session()
        elif msg_type == "interrupt":
            await self._interrupt()
        elif msg_type == "config":
            await self._update_config(data.get("config", {}))
            
    async def _process_audio_chunk(self, chunk: bytes):
        """Processa chunk de áudio recebido."""
        if not self.running:
            return
            
        self.audio_buffer.append(chunk)
        self.buffer_size += len(chunk)
        
        # Processar quando buffer estiver cheio
        if self.buffer_size >= self.max_buffer_size:
            await self._process_audio()
            
    async def _process_audio(self):
        """Processa áudio acumulado (STT)."""
        if not self.audio_buffer:
            return
            
        audio_data = b"".join(self.audio_buffer)
        self.audio_buffer.clear()
        self.buffer_size = 0
        
        # Enviar para STT
        try:
            from app.services.voice.pipeline import VoicePipeline
            pipeline = VoicePipeline(self.settings)
            
            # Transcrever
            text = pipeline.transcribe_bytes(audio_data)
            
            if text:
                await self.ws.send(json.dumps({
                    "type": "transcript",
                    "text": text,
                    "final": True
                }))
                
                # Obter resposta do LLM
                response = await self._get_llm_response(text)
                
                if response:
                    await self.ws.send(json.dumps({
                        "type": "response",
                        "text": response
                    }))
                    
                    # Gerar áudio via TTS streaming
                    await self._stream_tts(response)
                    
        except Exception as e:
            print(f"[VoiceWS] Erro ao processar áudio: {e}")
            
    async def _get_llm_response(self, text: str) -> str:
        """Obtém resposta do LLM."""
        try:
            from app.services.llm import LLMService
            llm = LLMService(self.settings)
            
            result = llm.chat(text)
            return result.get("reply", "") or result.get("summary", "")
            
        except Exception as e:
            print(f"[VoiceWS] Erro no LLM: {e}")
            return ""
            
    async def _stream_tts(self, text: str):
        """Envia áudio TTS em streaming."""
        try:
            from app.services.voice.pipeline import VoicePipeline
            pipeline = VoicePipeline(self.settings)
            
            # Usar streaming de TTS
            for chunk in pipeline.synthesize_stream(text):
                if chunk:
                    await self.ws.send(json.dumps({
                        "type": "audio_chunk",
                        "data": base64.b64encode(chunk).decode("utf-8")
                    }))
                    
            await self.ws.send(json.dumps({
                "type": "audio_end"
            }))
            
        except Exception as e:
            print(f"[VoiceWS] Erro no TTS streaming: {e}")
            
    async def _start_session(self):
        """Inicia sessão de voz."""
        self.audio_buffer.clear()
        self.buffer_size = 0
        await self.ws.send(json.dumps({
            "type": "session_started"
        }))
        
    async def _stop_session(self):
        """Para sessão de voz."""
        if self.audio_buffer:
            await self._process_audio()
        await self.ws.send(json.dumps({
            "type": "session_stopped"
        }))
        
    async def _interrupt(self):
        """Interrupção imediata (barge-in)."""
        self.audio_buffer.clear()
        self.buffer_size = 0
        await self.ws.send(json.dumps({
            "type": "interrupted"
        }))
        
    async def _update_config(self, config: dict):
        """Atualiza configuração."""
        await self.ws.send(json.dumps({
            "type": "config_updated",
            "config": config
        }))
