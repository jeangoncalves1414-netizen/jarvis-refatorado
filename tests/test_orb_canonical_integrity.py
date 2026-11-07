import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ORB_PATH = REPO_ROOT / "frontend" / "src" / "components" / "JarvisOrb3D.tsx"
DIST_HTML = REPO_ROOT / "frontend" / "dist" / "index.html"
MOBILE_ASSETS_DIR = REPO_ROOT / "mobile_app" / "app" / "src" / "main" / "assets"
MOBILE_HTML = MOBILE_ASSETS_DIR / "index.html"
APK_PATH = REPO_ROOT / "backups" / "jarvis_mobile_versao_oficial_ativa.apk"

def test_orb_component_has_quantum_arc_core():
    assert ORB_PATH.exists(), f"JarvisOrb3D.tsx deve existir em {ORB_PATH}"
    content = ORB_PATH.read_text(encoding="utf-8")
    assert "QUANTUM ARC" in content or "QUANTUM" in content, "Orbe deve ter identificador Quantum Arc Reactor Core"
    assert "00daf8" in content or "0, 218, 248" in content, "Orbe deve usar a paleta ciano holográfica oficial do Jarvis"

def test_orb_component_does_not_contain_3d_sphere():
    content = ORB_PATH.read_text(encoding="utf-8")
    assert "SphereGeometry" not in content, "Esferas Three.js SphereGeometry são estritamente proibidas"
    assert "MeshStandardMaterial" not in content, "Mesh standard 3D é estritamente proibido no JarvisOrb"

def test_no_raphael_yellow_runes():
    content = ORB_PATH.read_text(encoding="utf-8")
    assert "VOICE OF THE WORLD" not in content, "Runas amarelas do Raphael não devem estar presentes na Orbe"
    assert "buildRuneRingTexture" not in content, "Não deve haver texturas de runas amarelas"

# O build web não toca mobile_app/. A igualdade só vale depois de `npm run build:mobile`.
@pytest.mark.mobile_release
def test_mobile_assets_match_frontend_dist():
    if DIST_HTML.exists() and MOBILE_HTML.exists():
        dist_text = DIST_HTML.read_text(encoding="utf-8")
        mobile_text = MOBILE_HTML.read_text(encoding="utf-8")
        assert dist_text == mobile_text, "mobile_app/app/src/main/assets/index.html deve ser idêntico ao frontend/dist/index.html"

def test_backup_apk_exists_and_fresh():
    assert APK_PATH.exists(), "APK oficial de backup deve existir"
    assert APK_PATH.stat().st_size > 5_000_000, "APK deve ser um binário Android válido (> 5MB)"
