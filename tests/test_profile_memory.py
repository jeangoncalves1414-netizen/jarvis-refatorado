from app.services import profile_memory


def test_profile_memory_isolated_and_searchable(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_memory, "PROFILE_MEMORY_FILE", tmp_path / "profile_memories.json")
    monkeypatch.setattr(profile_memory, "DATA_DIR", tmp_path)
    store = profile_memory.ProfileMemoryStore()
    first = store.add("jean", "Prefere respostas curtas", kind="preference")
    store.add("jamille", "Estuda biologia", kind="fact")

    assert first and store.count("jean") == 1
    assert store.list("jean", query="respostas")[0]["id"] == first["id"]
    assert store.list("jean", query="biologia") == []


def test_profile_memory_delete_and_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_memory, "PROFILE_MEMORY_FILE", tmp_path / "profile_memories.json")
    monkeypatch.setattr(profile_memory, "DATA_DIR", tmp_path)
    store = profile_memory.ProfileMemoryStore()
    item = store.add("jean", "Uma anotação")
    assert item and store.delete("jean", item["id"])
    store.add("jean", "Outra anotação")
    assert store.clear("jean") == 1
    assert store.count("jean") == 0
