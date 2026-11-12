import io
import json
import wave
from types import SimpleNamespace

from app.storage.language_store import LanguageStore
from app.storage.tutor_store import TutorStore
from app.ui.panel.api.language import handle_language_post
from app.ui.panel.api.tutor import handle_tutor_post


def test_cloze_repeated_groups_and_independent_reverse(tmp_path):
    store = TutorStore(str(tmp_path))
    handler = SimpleNamespace(orchestrator=SimpleNamespace(tutor_store=store))
    def create(**fields):
        return handle_tutor_post("/api/tutor/flashcards", json.dumps(fields).encode(), handler)
    assert create(kind="cloze", front="{{c1::a}} {{c2::b}} {{c1::c}}", deck="A :: B", tags="x, x")[0] == 201
    assert create(kind="cloze", front="{{c1::broken")[0] == 400
    assert create(kind="reversed", front="one", back="um")[0] == 201
    a, b, direct, reverse = TutorStore(str(tmp_path)).get_flashcards()
    assert (a["front"], b["front"], b["back"]) == ("[…] b […]", "a […] c", "a b c")
    assert a["topic"] == "A::B" and a["tags"] == ["x"]
    assert direct["front"] == reverse["back"] and reverse["id"] != direct["id"]


def test_vocab_reversed_independent_and_idempotent(tmp_path):
    store = LanguageStore(str(tmp_path))
    original = store.add_vocabulary("egg", "ovo", reversed_card=True)
    assert store.add_vocabulary("egg", "ovo", reversed_card=True) == original
    direct, reverse = store.get_due_vocabulary()
    assert reverse["reverse_of"] == direct["id"]
    store.review_vocabulary(reverse["id"], 2)
    assert store.get_vocabulary()[0]["reps"] == 0
    assert store.get_progress()["stats"]["total_vocab"] == 1
    assert store.delete_vocabulary(original) and not store.get_vocabulary()


def test_ipa_validates_audio_before_accessing_provider():
    handler = SimpleNamespace(orchestrator=SimpleNamespace(llm_service=None))
    assert handle_language_post("/api/language/ipa", b"invalid", handler)[0] == 400
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", ""))
        out.writeframes(bytes(3200))
    assert handle_language_post("/api/language/ipa", buf.getvalue(), handler)[0] == 503
