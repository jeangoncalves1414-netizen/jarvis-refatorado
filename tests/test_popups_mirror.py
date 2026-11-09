"""Os modelos de popup do backend e do frontend são os mesmos (lote 6, Fase 3)."""
import re
from pathlib import Path

from app.agent.popups import POPUP_TEMPLATES

REGISTRY_TS = Path(__file__).resolve().parent.parent / "frontend" / "src" / "popups" / "registry.ts"


def test_template_ids_match_frontend_registry():
    source = REGISTRY_TS.read_text(encoding="utf-8")
    constants = dict(re.findall(r"export const (POPUP_\w+) = '([^']+)'", source))
    block = re.search(r"export const popupRegistry[^=]*=\s*\{(.*?)\n\}", source, re.S)
    assert block, "popupRegistry não encontrado em registry.ts"
    keys = re.findall(r"\[(POPUP_\w+)\]\s*:", block.group(1))
    frontend_ids = {constants[name] for name in keys}
    assert frontend_ids == set(POPUP_TEMPLATES)
