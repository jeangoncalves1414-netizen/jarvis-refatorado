"""Endpoint REST do FastAPI para gerenciamento do Memory Vault no Frontend."""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services.memory_vault import memory_vault

router = APIRouter(prefix="/api/vault", tags=["vault"])


class DailyLogPayload(BaseModel):
    entry: str
    category: str = "Atividade"


class NotePayload(BaseModel):
    title: str
    content: str
    folder: str = "04-Projects"


class ProfileFactPayload(BaseModel):
    fact: str


@router.get("/daily")
def get_daily_note():
    content = memory_vault.get_or_create_daily_note()
    path = str(memory_vault.get_today_note_path())
    return {"ok": True, "path": path, "content": content}


@router.post("/daily/log")
def add_daily_log(payload: DailyLogPayload):
    ok = memory_vault.append_daily_log(payload.entry, payload.category)
    return {"ok": ok}


@router.get("/profile")
def get_profile():
    content = memory_vault.get_user_profile()
    return {"ok": True, "content": content}


@router.post("/profile/fact")
def add_profile_fact(payload: ProfileFactPayload):
    ok = memory_vault.update_user_profile_fact(payload.fact)
    return {"ok": ok}


@router.get("/search")
def search_vault(q: str = Query("", description="Termo de pesquisa"), limit: int = 10):
    results = memory_vault.search_vault(q, limit=limit)
    return {"ok": True, "results": results}


@router.post("/notes")
def create_note(payload: NotePayload):
    path = memory_vault.save_note(payload.title, payload.content, payload.folder)
    return {"ok": True, "path": path}
