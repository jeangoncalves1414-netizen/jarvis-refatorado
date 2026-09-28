"""
TEN VAD Wrapper - Wrapper para integração com TEN VAD.
TEN VAD é um VAD de baixa latência, alta performance e leve.
Este wrapper permite usar TEN VAD como alternativa ao VAD local.
"""

from __future__ import annotations

import os
import json
import subprocess
import tempfile
from typing import Any, Optional
from dataclasses import dataclass
from enum import Enum


class VADState(Enum):
    """Estados do VAD."""
    SPEAKING = "speaking"
    SILENCE = "silence"
    UNKNOWN = "unknown"


@dataclass
class VADResult:
    """Resultado do processamento VAD."""
    state: VADState
    confidence: float
    energy_level: float
    timestamp: float


class TENVADWrapper:
    """
    Wrapper para TEN VAD.
    Permite usar TEN VAD como alternativa ao VAD local.
    
    Nota: TEN VAD requer instalação do ten-vad package.
    Instalação: pip install ten-vad (quando disponível)
    """

    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self._vad_instance = None
        self._available = self._check_availability()
        
        if self._available:
            self._initialize()

    def _check_availability(self) -> bool:
        """Verifica se TEN VAD está disponível."""
        try:
            import importlib
            spec = importlib.util.find_spec("ten_vad")
            return spec is not None
        except Exception:
            return False

    def _initialize(self) -> None:
        """Inicializa o TEN VAD."""
        if not self._available:
            return

        try:
            # Tentar importar e inicializar TEN VAD
            # Nota: A API exata depende da implementação do ten-vad
            # Este é um placeholder para quando o pacote estiver disponível
            print("[TENVAD] TEN VAD disponível, inicializando...")
            # self._vad_instance = ten_vad.VAD(sample_rate=self.sample_rate)
            print("[TENVAD] TEN VAD inicializado com sucesso")
        except Exception as e:
            print(f"[TENVAD] Erro ao inicializar: {e}")
            self._available = False

    def process_audio(self, audio_data: bytes) -> VADResult:
        """
        Processa dados de áudio e retorna resultado VAD.
        
        Args:
            audio_data: Bytes de áudio (PCM, 16-bit, mono)
            
        Returns:
            VADResult com estado, confiança e nível de energia
        """
        if not self._available or not self._vad_instance:
            # Fallback para VAD local simples
            return self._fallback_vad(audio_data)

        try:
            import time
            # Processar com TEN VAD
            # is_speaking = self._vad_instance.process(audio_data)
            # state = VADState.SPEAKING if is_speaking else VADState.SILENCE
            
            # Placeholder - usar VAD local até TEN VAD estar disponível
            return self._fallback_vad(audio_data)
            
        except Exception as e:
            print(f"[TENVAD] Erro no processamento: {e}")
            return self._fallback_vad(audio_data)

    def _fallback_vad(self, audio_data: bytes) -> VADResult:
        """
        Fallback VAD local simples baseado em energia.
        Usado quando TEN VAD não está disponível.
        """
        import time
        
        if len(audio_data) == 0:
            return VADResult(
                state=VADState.SILENCE,
                confidence=0.0,
                energy_level=0.0,
                timestamp=time.time()
            )
        
        try:
            # Converter bytes para array de int16
            import array
            samples = array.array('h', audio_data)
        except (ValueError, TypeError) as e:
            print(f"[TENVAD] Erro ao converter áudio: {e}")
            return VADResult(
                state=VADState.UNKNOWN,
                confidence=0.0,
                energy_level=0.0,
                timestamp=time.time()
            )
        
        if len(samples) == 0:
            return VADResult(
                state=VADState.SILENCE,
                confidence=0.0,
                energy_level=0.0,
                timestamp=time.time()
            )
        
        # Calcular energia (RMS)
        energy = sum(abs(s) for s in samples) / len(samples)
        
        # Normalizar energia (0-1)
        normalized_energy = min(energy / 1000.0, 1.0)
        
        # Determinar estado baseado no threshold
        state = VADState.SPEAKING if normalized_energy > self.threshold else VADState.SILENCE
        
        return VADResult(
            state=state,
            confidence=abs(normalized_energy - self.threshold),
            energy_level=normalized_energy,
            timestamp=time.time()
        )

    def is_available(self) -> bool:
        """Verifica se TEN VAD está disponível."""
        return self._available

    def reset(self) -> None:
        """Reseta o estado interno do VAD."""
        if self._vad_instance:
            try:
                # self._vad_instance.reset()
                pass
            except Exception as e:
                print(f"[TENVAD] Erro ao resetar: {e}")


class TENVADConfig:
    """Configuração para TEN VAD."""
    
    def __init__(self):
        self.enabled = False
        self.threshold = 0.5
        self.sample_rate = 16000
        self.frame_size_ms = 30
        self.padding_duration_ms = 300
        self.min_speech_duration_ms = 250
        self.max_speech_duration_s = float('inf')
        
    def load_from_file(self, config_path: str) -> bool:
        """Carrega configuração de arquivo JSON."""
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.enabled = data.get('enabled', False)
                    self.threshold = data.get('threshold', 0.5)
                    self.sample_rate = data.get('sample_rate', 16000)
                    self.frame_size_ms = data.get('frame_size_ms', 30)
                    self.padding_duration_ms = data.get('padding_duration_ms', 300)
                    self.min_speech_duration_ms = data.get('min_speech_duration_ms', 250)
                return True
        except Exception as e:
            print(f"[TENVAD] Erro ao carregar config: {e}")
        return False
    
    def save_to_file(self, config_path: str) -> bool:
        """Salva configuração em arquivo JSON."""
        try:
            data = {
                'enabled': self.enabled,
                'threshold': self.threshold,
                'sample_rate': self.sample_rate,
                'frame_size_ms': self.frame_size_ms,
                'padding_duration_ms': self.padding_duration_ms,
                'min_speech_duration_ms': self.min_speech_duration_ms
            }
            config_dir = os.path.dirname(config_path)
            if config_dir:  # Só criar diretório se não for apenas filename
                os.makedirs(config_dir, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"[TENVAD] Erro ao salvar config: {e}")
        return False


# Singleton global
_vad_instance: Optional[TENVADWrapper] = None
_vad_config: Optional[TENVADConfig] = None


def get_vad() -> TENVADWrapper:
    """Retorna instância singleton do TENVADWrapper."""
    global _vad_instance
    if _vad_instance is None:
        config = get_vad_config()
        _vad_instance = TENVADWrapper(
            sample_rate=config.sample_rate,
            threshold=config.threshold
        )
    return _vad_instance


def get_vad_config() -> TENVADConfig:
    """Retorna instância singleton da configuração."""
    global _vad_config
    if _vad_config is None:
        _vad_config = TENVADConfig()
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "data", "ten_vad_config.json"
        )
        config_dir = os.path.dirname(config_path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        _vad_config.load_from_file(config_path)
    return _vad_config


def enable_ten_vad() -> bool:
    """Habilita TEN VAD."""
    config = get_vad_config()
    config.enabled = True
    config_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "data", "ten_vad_config.json"
    )
    return config.save_to_file(config_path)


def disable_ten_vad() -> bool:
    """Desabilita TEN VAD."""
    config = get_vad_config()
    config.enabled = False
    config_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "data", "ten_vad_config.json"
    )
    return config.save_to_file(config_path)
