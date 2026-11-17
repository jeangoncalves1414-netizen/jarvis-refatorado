"""Captura de microfone no backend (SpeechRecognition + PyAudio) para a ligação por voz no PC.

Replica o motor do projeto antigo (energy_threshold 1100 com ajuste dinâmico, pausa 0,8 s,
mínimo 0,35 s), mas expõe nível/limiar e aceita parada imediata. O painel consulta os
eventos por long-poll (GET /api/voice/capture/events); essa consulta também é o heartbeat:
sem consulta por IDLE_TIMEOUT segundos o microfone é fechado.
"""
from __future__ import annotations

import math
import re
import sys
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

BASE_ENERGY = 1100          # limiar do projeto antigo (sensibilidade padrão 75)
DEFAULT_SENSITIVITY = 75
CHUNK = 1024
MAX_PHRASE_SECONDS = 20.0
MIN_AUDIO_SECONDS = 0.35
NON_SPEAKING_SECONDS = 0.35
DYNAMIC_DAMPING = 0.15
DYNAMIC_RATIO = 1.5
PLAYBACK_THRESHOLD_FACTOR = 3.0   # durante o TTS só voz bem alta interrompe
PLAYBACK_BARGE_SECONDS = 0.4      # e precisa durar este tempo
PLAYBACK_TAIL_SECONDS = 0.5       # cauda do eco depois que o TTS termina
IDLE_TIMEOUT = 25.0


def availability() -> tuple[bool, str]:
    try:
        import speech_recognition  # noqa: F401
    except ImportError:
        return False, "SpeechRecognition não instalado (pip install SpeechRecognition); a ligação usa o detector do navegador."
    try:
        import pyaudio  # noqa: F401
    except ImportError:
        return False, "PyAudio não instalado (pip install pyaudio); a ligação usa o detector do navegador."
    try:
        import audioop  # noqa: F401
    except ImportError:
        return False, "Módulo audioop ausente neste Python; a ligação usa o detector do navegador."
    return True, ""


def list_devices() -> dict[str, Any]:
    """Microfones de entrada (índice do PyAudio = device_index do sr.Microphone)."""
    import pyaudio
    audio = pyaudio.PyAudio()
    try:
        devices: list[dict[str, Any]] = []
        default_index = None
        host_api = None
        try:
            default_info = audio.get_default_input_device_info()
            default_index, host_api = int(default_info.get("index")), default_info.get("hostApi")
        except Exception:
            pass
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            # Só a API de áudio padrão: o Windows repete cada microfone em MME/WASAPI/WDM-KS.
            if host_api is not None and info.get("hostApi") != host_api:
                continue
            if int(info.get("maxInputChannels", 0) or 0) > 0:
                devices.append({"index": index, "name": str(info.get("name", f"Dispositivo {index}")), "default": index == default_index})
        return {"devices": devices, "default_index": default_index}
    finally:
        audio.terminate()


def match_input_device(name: str, devices: list[dict[str, Any]]) -> int | None:
    if not name:
        return None
    def normalize(label: str) -> str:
        # Chromium adds a USB vendor/product suffix absent from PortAudio names.
        return re.sub(r"\s*\([0-9a-f]{4}:[0-9a-f]{4}\)$", "", label.casefold()).strip()
    wanted = normalize(name)
    matches = [d for d in devices if normalize(d["name"]) == wanted]
    if not matches:
        # Windows MME truncates device names to 31 characters. Never guess if ambiguous.
        matches = [d for d in devices if len(normalize(d["name"])) == 31 and wanted.startswith(normalize(d["name"]))]
    if len(matches) != 1:
        raise ValueError("Microfone selecionado indisponível ou ambíguo. Escolha o dispositivo novamente nas configurações.")
    return int(matches[0]["index"])


def resolve_device_index(name: str | None = None) -> int | None:
    if name is None:
        from app.storage.runtime_settings import get_mic_settings
        name = get_mic_settings()["device_name"]
    return match_input_device(name, list_devices()["devices"]) if name else None


def energy_threshold_for(sensitivity: float, gain: float = 1.0) -> int:
    """Slider 1-100 -> energy_threshold. 75 = 1100 (projeto antigo); cada -25 dobra o limiar."""
    value = BASE_ENERGY * 2 ** ((DEFAULT_SENSITIVITY - float(sensitivity)) / 25.0) / max(0.5, float(gain))
    return int(max(150, min(8000, value)))


def _pause_wake_word(paused: bool) -> None:
    server = sys.modules.get("app.ui.panel.server")
    detector = getattr(server, "_wake_word_detector", None) if server else None
    if detector is not None and hasattr(detector, "set_mic_paused"):
        try:
            detector.set_mic_paused(paused)
        except Exception:
            pass


class MicCapture:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._events: deque[dict[str, Any]] = deque(maxlen=400)
        self._seq = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._active = False
        self._last_poll = 0.0
        self._playing = False
        self._mute_until = 0.0
        self._state = "idle"
        self._thr = float(BASE_ENERGY)
        self._base_thr = float(BASE_ENERGY)
        self._device_name = ""
        self._start_lock = threading.Lock()
        self._generation = 0
        self._neural = None
        self._semantic_requested = False

    # ── eventos ──────────────────────────────────────────────────────────────
    def _emit(self, kind: str, **data: Any) -> int:
        with self._cond:
            self._seq += 1
            self._events.append({"seq": self._seq, "type": kind, **data})
            self._cond.notify_all()
            return self._seq

    def _set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self._emit("state", state=state)

    def events(self, after: int = 0, wait: float = 0.0) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.0, min(wait, 10.0))
        with self._cond:
            self._last_poll = time.monotonic()
            while True:
                items = [event for event in self._events if event["seq"] > after]
                remaining = deadline - time.monotonic()
                if items or remaining <= 0 or not self._active:
                    break
                self._cond.wait(remaining)
                self._last_poll = time.monotonic()
            return {"events": items, "seq": self._seq, "active": self._active, "state": self._state}

    def status(self) -> dict[str, Any]:
        return {"active": self._active, "state": self._state, "threshold": int(self._thr), "device": self._device_name, "seq": self._seq, "turn_detector": "smart-turn-v3.2" if self._neural else "silence"}

    @property
    def active(self) -> bool:
        return self._active

    # ── controle ─────────────────────────────────────────────────────────────
    def start(self, *, sensitivity: float, silence_ms: float, gain: float, device_name: str,
              transcribe: Callable[[bytes], dict[str, Any]], semantic_turns: bool = False) -> dict[str, Any]:
        ok, reason = availability()
        if not ok:
            return {"ok": False, "error": reason}
        with self._start_lock:
            self.stop()
            if self._thread is not None and self._thread.is_alive():
                return {"ok": False, "error": "A captura anterior ainda está encerrando."}
            self._semantic_requested = semantic_turns
            try:
                device_index = resolve_device_index(device_name)
            except (ValueError, OSError) as exc:
                return {"ok": False, "error": str(exc)}
            self._base_thr = float(energy_threshold_for(sensitivity, gain))
            self._thr = self._base_thr
            self._device_name = device_name
            self._playing = False
            self._mute_until = 0.0
            self._stop.clear()
            self._last_poll = time.monotonic()
            self._state = "idle"
            self._active = True
            baseline = self._seq
            ready = threading.Event()
            info: dict[str, Any] = {}
            _pause_wake_word(True)
            thread = threading.Thread(
                target=self._run, name="mic-capture", daemon=True,
                args=(device_index, max(0.25, min(3.0, silence_ms / 1000.0)), transcribe, ready, info),
            )
            self._thread = thread
            thread.start()
            if not ready.wait(6.0):
                self._stop.set()
                return {"ok": False, "error": "O microfone do PC não abriu a tempo."}
            if info.get("error"):
                return {"ok": False, "error": info["error"]}
            return {"ok": True, "seq": baseline, "threshold": int(self._thr), "base_threshold": int(self._base_thr), "turn_detector": "smart-turn-v3.2" if self._neural else "silence", "turn_detector_warning": info.get("turn_detector_warning", "")}

    def stop(self) -> None:
        self._generation += 1
        thread = self._thread
        self._stop.set()
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(3.0)
        if thread is None or not thread.is_alive():
            self._thread = None
        if self._active and (thread is None or not thread.is_alive()):
            self._active = False
            _pause_wake_word(False)

    def set_playback(self, active: bool) -> None:
        self._playing = bool(active)
        if not active:
            self._mute_until = time.monotonic() + PLAYBACK_TAIL_SECONDS

    # ── thread de captura ────────────────────────────────────────────────────
    def _run(self, device_index: int | None, silence_s: float, transcribe: Callable[[bytes], dict[str, Any]],
             ready: threading.Event, info: dict[str, Any]) -> None:
        import speech_recognition as sr
        try:
            if self._semantic_requested:
                try:
                    from .turn_audio import NeuralTurnDetector
                    self._neural = NeuralTurnDetector()
                except Exception as exc:
                    info["turn_detector_warning"] = str(exc)
                    self._emit("detector_warning", message="Detector neural indisponível; usando modo de escuta simples.")
            with sr.Microphone(device_index=device_index, chunk_size=CHUNK) as source:
                ready.set()
                self._set_state("calibrating")
                self._calibrate(source)
                self._set_state("listening")
                self._loop(source, silence_s, transcribe)
        except Exception as exc:  # noqa: BLE001 - qualquer falha de dispositivo vira evento
            message = f"Falha no microfone do PC: {exc}"
            info["error"] = message
            self._emit("error", message=message, fatal=True)
        finally:
            self._neural = None
            ready.set()
            self._active = False
            self._state = "idle"
            self._emit("stopped")
            _pause_wake_word(False)

    def _adjust(self, energy: float, seconds_per_buffer: float, floor: float) -> None:
        damping = DYNAMIC_DAMPING ** seconds_per_buffer
        target = energy * DYNAMIC_RATIO
        self._thr = max(floor, self._thr * damping + target * (1 - damping))

    def _calibrate(self, source: Any) -> None:
        import audioop
        spb = CHUNK / source.SAMPLE_RATE
        elapsed = 0.0
        while elapsed < 0.8 and not self._stop.is_set():
            buf = source.stream.read(CHUNK)
            elapsed += spb
            self._adjust(audioop.rms(buf, source.SAMPLE_WIDTH), spb, 0.0)
        self._thr = max(self._thr, self._base_thr)  # nunca abaixo do configurado
        self._emit("calibrated", threshold=int(self._thr), base_threshold=int(self._base_thr))

    def _loop(self, source: Any, silence_s: float, transcribe: Callable[[bytes], dict[str, Any]]) -> None:
        # Neural inference must never block microphone reads.
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="turn-detector") as worker:
            self._capture_loop(source, silence_s, transcribe, worker)

    def _capture_loop(self, source: Any, silence_s: float, transcribe: Callable[[bytes], dict[str, Any]], worker: ThreadPoolExecutor) -> None:
        import audioop
        from .turn_audio import endpoint_ready
        rate, width = source.SAMPLE_RATE, source.SAMPLE_WIDTH
        spb = CHUNK / rate
        pause_buf = math.ceil(silence_s / spb)
        min_buf = math.ceil(MIN_AUDIO_SECONDS / spb)
        pre_buf = math.ceil(NON_SPEAKING_SECONDS / spb)
        barge_buf = math.ceil(PLAYBACK_BARGE_SECONDS / spb)
        max_buf = math.ceil(MAX_PHRASE_SECONDS / spb)
        floor = self._base_thr * 0.5
        pre: deque[bytes] = deque()
        frames: list[bytes] = []
        speaking = False
        speech_cnt = quiet_cnt = loud_run = 0
        last_level = 0.0
        prediction = None
        prediction_epoch = 0
        speech_epoch = 0
        probability = None
        evaluated_pause = False

        while not self._stop.is_set():
            now = time.monotonic()
            if now - self._last_poll > IDLE_TIMEOUT:
                self._emit("error", message="A tela parou de consultar o microfone; captura encerrada.", fatal=True)
                break
            buf = source.stream.read(CHUNK)
            if not buf:
                break
            energy = audioop.rms(buf, width)
            voice_probability = self._neural.speech_probability(buf, rate, width) if self._neural else None
            playing = self._playing or now < self._mute_until
            thr = self._thr * (PLAYBACK_THRESHOLD_FACTOR if playing else 1.0)
            if now - last_level >= 0.1:
                last_level = now
                self._emit("level", level=int(energy), threshold=int(thr), playing=playing, speech_probability=voice_probability)

            if not speaking:
                pre.append(buf)
                while len(pre) > pre_buf + (barge_buf if playing else 0):
                    pre.popleft()
                # Neural VAD rejects many clicks/noises. During speaker playback keep an echo gate.
                voiced = (voice_probability >= 0.65 and (not playing or energy > self._thr * 1.5)) if voice_probability is not None else energy > thr
                if voiced:
                    loud_run += 1
                    if playing and loud_run < barge_buf:
                        continue
                    if self._playing:
                        self._playing = False
                        self._emit("barge_in")
                    speaking = True
                    frames = list(pre)
                    pre.clear()
                    speech_cnt, quiet_cnt = loud_run, 0
                    speech_epoch += 1
                    probability, evaluated_pause = None, False
                    self._set_state("speaking")
                else:
                    loud_run = 0
                    if not playing:
                        self._adjust(energy, spb, floor)
                continue

            frames.append(buf)
            if (voice_probability >= 0.5 if voice_probability is not None else energy > self._thr):
                if quiet_cnt:
                    speech_epoch += 1
                probability, evaluated_pause = None, False
                speech_cnt += 1
                quiet_cnt = 0
            else:
                quiet_cnt += 1
            if prediction is not None and prediction.done():
                try:
                    result = prediction.result()
                    if prediction_epoch == speech_epoch:
                        probability = result
                        self._emit("turn_prediction", probability=round(result, 4), detector="smart-turn-v3.2")
                except Exception:
                    self._emit("detector_warning", message="Não consegui avaliar esta pausa; vou aguardar mais tempo.")
                prediction = None
            if self._neural and quiet_cnt * spb >= 0.45 and not evaluated_pause and prediction is None:
                # Preserve prosody at the end of speech; don't feed ever-growing silence.
                prediction_epoch = speech_epoch
                snapshot = b"".join(frames[-math.ceil(8.0 / spb):])
                prediction = worker.submit(self._neural.completion_probability, snapshot, rate, width)
                evaluated_pause = True
            complete = endpoint_ready(quiet_cnt * spb, probability) if self._neural else quiet_cnt > pause_buf
            if complete or len(frames) >= max_buf:
                kept = frames[: max(1, len(frames) - quiet_cnt + pre_buf)]
                if speech_cnt >= min_buf:
                    self._submit(b"".join(kept), rate, width, transcribe, spb * len(kept), turn_complete=complete)
                elif complete and self._neural:
                    self._emit("turn_end")
                if not complete:
                    # A size limit is a transcription segment, never permission to answer.
                    frames, speech_cnt = [], 0
                    continue
                frames, speaking = [], False
                speech_cnt = quiet_cnt = loud_run = 0
                pre.clear()
                self._set_state("listening")

    def _submit(self, raw: bytes, rate: int, width: int, transcribe: Callable[[bytes], dict[str, Any]], seconds: float, turn_complete: bool = True) -> None:
        turn_id = uuid.uuid4().hex[:12]
        self._emit("processing", turn_id=turn_id, audio_seconds=round(seconds, 2))
        threading.Thread(target=self._transcribe, args=(turn_id, raw, rate, width, transcribe, self._generation, turn_complete), daemon=True, name="mic-stt").start()

    def _transcribe(self, turn_id: str, raw: bytes, rate: int, width: int, transcribe: Callable[[bytes], dict[str, Any]], generation: int | None = None, turn_complete: bool = True) -> None:
        import speech_recognition as sr
        started = time.monotonic()
        try:
            wav = sr.AudioData(raw, rate, width).get_wav_data(convert_rate=16000, convert_width=2)
            result = transcribe(wav) or {}
        except Exception as exc:  # noqa: BLE001
            if generation is not None and generation != self._generation:
                return
            self._emit("empty", turn_id=turn_id, error=f"Falha ao transcrever: {exc}", stt_ms=int((time.monotonic() - started) * 1000))
            return
        if generation is not None and generation != self._generation:
            return
        stt_ms = int((time.monotonic() - started) * 1000)
        text = str(result.get("text") or "").strip()
        if result.get("ok") and text:
            self._emit("transcript", turn_id=turn_id, text=text, stt_ms=stt_ms, turn_complete=turn_complete, semantic=bool(self._neural), speaker=result.get("speaker"))
        else:
            self._emit("empty", turn_id=turn_id, error=result.get("error") or "", stt_ms=stt_ms)


capture = MicCapture()
