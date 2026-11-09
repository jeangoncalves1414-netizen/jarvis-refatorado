"""Testes de Checklists Inteligentes (estilo Google Keep) com parser de linguagem natural e sink behavior.

100% isolado de data/ real, utilizando tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.agent.tools.checklist_tool import ChecklistTool
from app.storage.checklist_store import ChecklistStore, parse_spoken_items
from app.ui.panel.api.checklists import handle_checklists_get, handle_checklists_post


@pytest.fixture
def isolated_checklist_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Instância isolada de ChecklistStore em arquivo temporário."""
    db_file = tmp_path / "checklists.sqlite3"
    store = ChecklistStore(db_file)
    monkeypatch.setattr("app.storage.checklist_store.checklist_store", store)
    monkeypatch.setattr("app.agent.tools.checklist_tool.checklist_store", store)
    monkeypatch.setattr("app.ui.panel.api.checklists.checklist_store", store)
    return store


def test_parse_spoken_items_complex():
    """Testa o parser inteligente de linguagem natural falada/escrita."""
    raw = "1 saco de arroz, 10 batatas chips, 2 coca colas se tiver abaixo de 10 reais, 5 batatas inglesas"
    items = parse_spoken_items(raw)
    assert len(items) == 4

    # Item 1: 1 saco de arroz
    assert items[0]["text"] == "arroz"
    assert items[0]["quantity"] == "1 saco"
    assert items[0]["condition_note"] == ""

    # Item 2: 10 batatas chips
    assert items[1]["text"] == "batatas chips"
    assert items[1]["quantity"] == "10"
    assert items[1]["condition_note"] == ""

    # Item 3: 2 coca colas se tiver abaixo de 10 reais
    assert items[2]["text"] == "coca colas"
    assert items[2]["quantity"] == "2"
    assert "se tiver abaixo de 10 reais" in items[2]["condition_note"]

    # Item 4: 5 batatas inglesas
    assert items[3]["text"] == "batatas inglesas"
    assert items[3]["quantity"] == "5"
    assert items[3]["condition_note"] == ""


def test_parse_spoken_items_variations():
    """Testa variações adicionais de unidades, multiplicadores e condições."""
    raw = "2x café se em promoção, 500g queijo mussarela, 3 garrafas de vinho caso custe menos de 50 reais, pão de queijo"
    items = parse_spoken_items(raw)
    assert len(items) == 4

    assert items[0]["text"] == "café"
    assert items[0]["quantity"] == "2x"
    assert "promoção" in items[0]["condition_note"]

    assert items[1]["text"] == "queijo mussarela"
    assert items[1]["quantity"] == "500g"

    assert items[2]["text"] == "vinho"
    assert items[2]["quantity"] == "3 garrafas"
    assert "caso custe menos de 50 reais" in items[2]["condition_note"]

    assert items[3]["text"] == "pão de queijo"
    assert items[3]["quantity"] == ""
    assert items[3]["condition_note"] == ""


def test_checklist_store_crud_and_sink(isolated_checklist_store: ChecklistStore):
    """Testa operações básicas e o comportamento de Sink (itens concluídos afundam para o rodapé)."""
    store = isolated_checklist_store

    # 1. Cria lista com texto livre falado
    created = store.create_list("Supermercado", items="1 saco de arroz, 2 coca colas, feijão preto")
    assert created["title"] == "Supermercado"
    list_id = created["id"]
    assert len(created["items"]) == 3
    assert created["pending_count"] == 3
    assert created["completed_count"] == 0

    # Pega os IDs dos itens
    items = created["items"]
    arroz_id = items[0]["id"]
    coca_id = items[1]["id"]
    feijao_id = items[2]["id"]

    # 2. Conclui o primeiro item (arroz) -> deve afundar para o final
    toggled = store.toggle_item(arroz_id)
    assert toggled is not None
    assert toggled["completed"] is True

    # Verifica ordenação com afundamento (Sink): coca e feijao primeiro, arroz ao final
    refetched = store.get_list(list_id)
    assert refetched is not None
    assert refetched["pending_count"] == 2
    assert refetched["completed_count"] == 1

    item_texts = [it["text"] for it in refetched["items"]]
    assert item_texts == ["coca colas", "feijão preto", "arroz"]
    assert refetched["items"][0]["completed"] is False
    assert refetched["items"][1]["completed"] is False
    assert refetched["items"][2]["completed"] is True

    # 3. Conclui a coca cola também
    store.toggle_item(coca_id)
    refetched2 = store.get_list(list_id)
    item_texts2 = [it["text"] for it in refetched2["items"]]
    # feijão preto (único pendente) deve ser o primeiro, e os dois concluídos afundados
    assert item_texts2[0] == "feijão preto"
    assert set(item_texts2[1:]) == {"arroz", "coca colas"}

    # 4. Desmarca arroz -> deve voltar a flutuar para os pendentes
    store.toggle_item(arroz_id)
    refetched3 = store.get_list(list_id)
    assert refetched3["pending_count"] == 2
    assert refetched3["completed_count"] == 1
    # feijão e arroz estão pendentes (no topo), coca está concluída (no rodapé)
    pendings = [it["text"] for it in refetched3["items"] if not it["completed"]]
    assert "arroz" in pendings
    assert "feijão preto" in pendings
    assert refetched3["items"][-1]["text"] == "coca colas"


def test_checklist_tool(isolated_checklist_store: ChecklistStore):
    """Testa a ferramenta de agente ChecklistTool no Action Kernel."""
    tool = ChecklistTool()

    # 1. create_list
    res_create = tool.run(
        action="create_list",
        title="Mala de Viagem",
        text="3 camisetas, 2 bermudas, protetor solar se estiver calor",
    )
    assert res_create["ok"] is True
    list_id = res_create["list_id"]
    assert len(res_create["checklist"]["items"]) == 3

    # 2. get_list
    res_get = tool.run(action="get_list", list_id=list_id)
    assert res_get["ok"] is True
    assert res_get["checklist"]["title"] == "Mala de Viagem"

    # 3. add_items
    res_add = tool.run(
        action="add_items",
        list_id=list_id,
        text="1 óculos de sol, escova de dentes",
    )
    assert res_add["ok"] is True
    assert len(res_add["added_items"]) == 2

    # 4. toggle_item por nome aproximado
    res_toggle = tool.run(
        action="toggle_item",
        list_id=list_id,
        text="camisetas",
    )
    assert res_toggle["ok"] is True
    assert res_toggle["item"]["completed"] is True

    # 5. list_all
    res_all = tool.run(action="list_all")
    assert res_all["ok"] is True
    assert len(res_all["checklists"]) == 1

    # 6. delete_list
    res_del = tool.run(action="delete_list", list_id=list_id)
    assert res_del["ok"] is True
    assert tool.run(action="get_list", list_id=list_id)["ok"] is False


def test_checklist_api_routes(isolated_checklist_store: ChecklistStore):
    """Testa as rotas de API HTTP GET/POST para checklists."""
    # 1. POST /api/checklists
    body_create = json.dumps({
        "title": "Churrasco",
        "text": "2kg de picanha, 1 saco de carvão, 6 cervejas se estiver abaixo de 5 reais",
    }).encode("utf-8")
    status, data = handle_checklists_post("/api/checklists", body_create, None)
    assert status == 201
    assert data["ok"] is True
    checklist = data["checklist"]
    list_id = checklist["id"]
    assert len(checklist["items"]) == 3

    # 2. GET /api/checklists
    status, data_get = handle_checklists_get(["api", "checklists"], None)
    assert status == 200
    assert len(data_get["checklists"]) == 1

    # 3. GET /api/checklists/{id}
    status, data_one = handle_checklists_get(["api", "checklists", list_id], None)
    assert status == 200
    assert data_one["checklist"]["title"] == "Churrasco"

    # 4. POST /api/checklists/{id}/items
    body_items = json.dumps({"text": "pão de alho, vinagrete"}).encode("utf-8")
    status, data_added = handle_checklists_post(f"/api/checklists/{list_id}/items", body_items, None)
    assert status == 200
    assert len(data_added["added"]) == 2
    assert len(data_added["checklist"]["items"]) == 5

    # 5. POST /api/checklists/{id}/toggle
    item_id = data_added["added"][0]["id"]
    body_toggle = json.dumps({"item_id": item_id, "completed": True}).encode("utf-8")
    status, data_toggled = handle_checklists_post(f"/api/checklists/{list_id}/toggle", body_toggle, None)
    assert status == 200
    assert data_toggled["item"]["completed"] is True

    # 6. POST /api/checklists/{id}/delete
    status, data_deleted = handle_checklists_post(f"/api/checklists/{list_id}/delete", b"{}", None)
    assert status == 200
    assert data_deleted["ok"] is True
