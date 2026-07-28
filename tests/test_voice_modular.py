from __future__ import annotations

import os
import pytest
from app.services.voice.tts.cleaner import strip_text_for_speech
from app.services.voice.tts.prefetch import split_text_for_tts
from app.services.voice.tts.cache import TTSCache
from app.services.voice.stt.filter import filter_stt_hallucinations


def test_strip_text_for_speech():
    raw = "## Olá! **Este** é um [link](http://example.com) com `código` e emoji 😊. [tool:open_windows_app:chrome]"
    cleaned = strip_text_for_speech(raw)
    assert "Olá!" in cleaned
    assert "Este" in cleaned
    assert "link" in cleaned
    assert "http" not in cleaned
    assert "tool:" not in cleaned
    assert "😊" not in cleaned
    assert "**" not in cleaned
    assert "`" not in cleaned


def test_split_text_for_tts():
    long_text = "Primeira frase. Segunda frase! Terceira frase? Quarta frase com mais texto para testar o particionador de voz."
    chunks = split_text_for_tts(long_text, max_chars=40)
    assert len(chunks) > 1
    assert "".join(chunks).replace(" ", "") == long_text.replace(" ", "")


def test_tts_cache(tmp_path):
    cache = TTSCache(cache_dir=tmp_path)
    text = "Frase de teste para cache"
    voice = "pt-BR-FranciscaNeural"

    # Inicialmente não está no cache
    assert cache.get_cached_file(text, voice) is None

    # Cria arquivo dummy
    dummy_file = tmp_path / "dummy.mp3"
    dummy_file.write_bytes(b"dummy audio data")

    # Salva no cache
    cached_path = cache.save_to_cache(text, voice, dummy_file)
    assert cached_path.exists()

    # Agora deve retornar do cache
    found = cache.get_cached_file(text, voice)
    assert found is not None
    assert found.exists()


def test_filter_stt_hallucinations():
    # Teste de alucinação severa (hard)
    assert filter_stt_hallucinations("legendas por sônia ruberti") == ""
    assert filter_stt_hallucinations("Inscreva-se no canal!") == ""

    # Teste de alucinação leve em silêncio (soft)
    assert filter_stt_hallucinations("obrigado") == ""
    assert filter_stt_hallucinations("hmmm") == ""

    # Teste de fala legítima do usuário
    valid = "Jarvis, abra o navegador por favor"
    assert filter_stt_hallucinations(valid) == valid
