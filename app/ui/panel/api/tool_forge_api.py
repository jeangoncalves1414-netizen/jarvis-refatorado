"""API REST do FastAPI para o Tool Forge Visual."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.tool_forge import tool_forge
from app.services.llm import LLMService

router = APIRouter(prefix="/api/tool-forge", tags=["tool-forge"])


class GenerateToolRequest(BaseModel):
    tool_name: str
    description: str


class InstallToolRequest(BaseModel):
    tool_name: str
    code: str


@router.get("/list")
def list_tools():
    tools = tool_forge.list_custom_tools()
    return {"ok": True, "tools": tools}


@router.post("/generate")
def generate_tool(payload: GenerateToolRequest):
    prompt = (
        f"Crie o código Python interno para uma ferramenta do assistente chamada '{payload.tool_name}'.\n"
        f"Descrição da ferramenta: {payload.description}\n\n"
        "Retorne apenas o bloco de código Python que deve ir dentro do método run(). "
        "O código deve retornar um dicionário dict com {'success': True, 'data': ...} ou raise Exception.\n"
        "Não inclua preâmbulos nem marcas markdown de ```python no início/fim."
    )
    llm = LLMService()
    raw_code = llm.ask(prompt)
    
    # Limpa marcadores de código se o LLM incluir
    clean_code = raw_code.replace("```python", "").replace("```", "").strip()
    full_template = tool_forge.generate_tool_template(payload.tool_name, payload.description, clean_code)
    valid, msg = tool_forge.validate_code_ast(full_template)
    
    return {
        "ok": valid,
        "message": msg,
        "tool_name": payload.tool_name,
        "code": full_template
    }


@router.post("/install")
def install_tool(payload: InstallToolRequest):
    success, message = tool_forge.save_and_register_tool(payload.tool_name, payload.code)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}
