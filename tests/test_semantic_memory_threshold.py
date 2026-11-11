"""Índice semântico: user_memory sem expiração, limite de distância e access_count pelo id do Chroma."""
import time
from pathlib import Path

import pytest

from app.storage.vector import semantic_memory as module
from app.storage.vector.semantic_memory import USER_MEMORY_MAX_DISTANCE, SemanticMemory


class FakeCollection:
    def __init__(self):
        self.updates = []
        old = time.time() - 400 * 86400
        self.result = {
            "ids": [["chroma-1", "chroma-2"]],
            "documents": [["O usuário criou o sistema Jarvis", "vai dar comida apenas de manhã e à noite"]],
            "metadatas": [[{"timestamp": old, "importance": 1.0}, {"timestamp": old, "importance": 1.0}]],
            "distances": [[0.17, 0.57]],
        }

    def query(self, **_kwargs):
        return self.result

    def update(self, ids, metadatas):
        self.updates.append((ids, metadatas))


def _memory(tmp_path):
    memory = SemanticMemory.__new__(SemanticMemory)
    memory.persist_dir, memory.max_age_days, memory.client = tmp_path, 90, object()
    collection = FakeCollection()
    memory._collections = {"user_memory": collection, "conversations": collection}
    return memory, collection


def test_user_memory_does_not_expire_and_threshold_drops_far_results(tmp_path):
    memory, collection = _memory(tmp_path)
    assert [m["distance"] for m in memory.search_memories("user_memory", "quem criou o Jarvis?")] == [0.17, 0.57]
    assert memory.search_memories("conversations", "quem criou o Jarvis?") == []
    near = memory.search_memories("user_memory", "quem criou o Jarvis?", max_distance=USER_MEMORY_MAX_DISTANCE)
    assert [m["text"] for m in near] == ["O usuário criou o sistema Jarvis"]
    assert collection.updates[-1][0] == ["chroma-1"]
    assert collection.updates[-1][1][0]["access_count"] == 1


def test_embedding_function_is_single_switch_point(monkeypatch, tmp_path):
    calls = []

    class Client:
        def get_or_create_collection(self, **kwargs):
            calls.append(kwargs)
            return object()

    memory = SemanticMemory.__new__(SemanticMemory)
    memory.client, memory._collections = Client(), {}
    memory.get_or_create_collection("a")
    assert "embedding_function" not in calls[-1]
    sentinel = object()
    monkeypatch.setattr(module, "embedding_function", lambda: sentinel)
    memory.get_or_create_collection("b")
    assert calls[-1]["embedding_function"] is sentinel


_ONNX = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"


@pytest.mark.skipif(not module.CHROMADB_AVAILABLE or not _ONNX.exists(), reason="Chroma ou modelo ONNX ausente")
def test_real_chroma_threshold_with_report_phrases(tmp_path):
    memory = SemanticMemory(persist_dir=str(tmp_path / "vector"))
    assert memory.add_memory("user_memory", "O usuário criou o sistema Jarvis", metadata={"fact_id": "mem_a"})
    assert memory.add_memory("user_memory", "vai dar comida apenas de manhã e à noite", metadata={"fact_id": "mem_b"})
    found = memory.search_memories("user_memory", "quem criou o Jarvis?", max_distance=USER_MEMORY_MAX_DISTANCE)
    assert [m["text"] for m in found] == ["O usuário criou o sistema Jarvis"]
    food = memory.search_memories("user_memory", "qual comida eu gosto?", max_distance=USER_MEMORY_MAX_DISTANCE)
    assert "vai dar comida apenas de manhã e à noite" not in [m["text"] for m in food]
    assert memory.delete_where("user_memory", {"fact_id": "mem_a"}) == 1
    assert memory.search_memories("user_memory", "quem criou o Jarvis?", max_distance=USER_MEMORY_MAX_DISTANCE) == []
