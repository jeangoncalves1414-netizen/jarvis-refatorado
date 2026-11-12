from app.storage import session_store as store


def test_selected_chat_trash_and_undo_are_idempotent_and_preserve_study():
    for session in ({"id": "old"}, {"id": "new", "type": "chat"}, {"id": "study", "type": "tutor"}):
        store.add_session(session)
    store.save_session_history("old", [{"role": "user", "content": "Olá"}])
    ids = ["old", "new", "study", "old"]
    assert store.change_chat_trash(ids) == ["old", "new"]
    assert store.change_chat_trash(ids) == []
    assert [s["id"] for s in store.list_sessions()] == ["study"]
    assert store.change_chat_trash(ids, restore=True) == ["old", "new"]
    assert store.get_session_history("old")[0]["content"] == "Olá"
