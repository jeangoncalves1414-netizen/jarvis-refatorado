from app.services.voice.tts.emotions import add_emotion_cues


def test_s2_emotion_cues_are_added_without_changing_plain_sentences():
    result = add_emotion_cues("Olá! Excelente, o sistema está pronto!")
    assert result.startswith("[warmly]")
    assert "[excited]" in result


def test_existing_cue_is_preserved_and_s1_uses_parentheses():
    assert add_emotion_cues("[whisper] Fale baixo.") == "[whisper] Fale baixo."
    assert add_emotion_cues("Cuidado!", model="s1") == "(concerned) Cuidado!"


def test_emotions_can_be_disabled():
    assert add_emotion_cues("Olá!", enabled=False) == "Olá!"
