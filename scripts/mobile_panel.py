"""Prepare Android's TLS trust and provision the panel credential over USB."""
import argparse
import json
import os
import secrets
import subprocess
import sys
from ipaddress import IPv4Address
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

# Allow both ``python scripts/mobile_panel.py`` and module execution. Python
# otherwise places ``scripts/`` (rather than the repository root) on sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding

from app.ui.panel.paired import DIRECTORY, PORT
from scripts.sync_mobile_routine import PACKAGE

RES = ROOT / "mobile_app/app/src/localPanel/res"


def _adb_target():
    return ["adb", "-s", os.environ["ADB_SERIAL"]] if os.environ.get("ADB_SERIAL") else ["adb", "-d"]


def _write_device_config(origin: str, token: str, mode: str):
    data = json.dumps({"origin": origin, "token": token, "mode": mode}).encode()
    adb_target = _adb_target()
    subprocess.run([*adb_target, "exec-in", "run-as", PACKAGE, "tee", "files/panel.tmp"],
                   input=data, stdout=subprocess.DEVNULL, check=True)
    subprocess.run([*adb_target, "shell", "run-as", PACKAGE, "mv", "files/panel.tmp", "files/panel.json"], check=True)


def provision(action):
    host = str(IPv4Address(json.loads((DIRECTORY / "config.json").read_text())["address"]))
    cert = x509.load_pem_x509_certificate((DIRECTORY / "tls.pem").read_bytes())
    if IPv4Address(host) not in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress):
        raise ValueError("Repita o pareamento Wi-Fi para este endereço.")
    origin = f"https://{host}:{PORT}"
    token_path = DIRECTORY / "panel-token"
    if action == "prepare":
        for folder in ("xml", "raw", "values"):
            (RES / folder).mkdir(parents=True, exist_ok=True)
        (RES / "raw/panel_certificate.pem").write_bytes(cert.public_bytes(Encoding.PEM))
        (RES / "xml/panel_network.xml").write_text(
            f'<network-security-config><domain-config cleartextTrafficPermitted="false"><domain includeSubdomains="true">{host}</domain>'
            '<trust-anchors><certificates src="@raw/panel_certificate"/></trust-anchors>'
            '</domain-config></network-security-config>')
        (RES / "values/panel.xml").write_text(f'<resources><string name="panel_origin">{origin}</string><string name="panel_mode">paired</string></resources>')
    else:
        token = token_path.read_text().strip() if token_path.exists() else secrets.token_urlsafe(32)
        _write_device_config(origin, token, "paired")
        if not token_path.exists():
            with token_path.open("x") as out:
                out.write(token)


def cloud(action: str, origin: str | None, token_env: str) -> None:
    if not origin:
        raise ValueError("Informe --origin https://seu-dominio.up.railway.app")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("A origem deve ser uma URL HTTPS sem caminho, por exemplo https://jarvis.up.railway.app")
    origin = f"https://{parsed.netloc}"
    if action == "prepare-cloud":
        for folder in ("xml", "values"):
            (RES / folder).mkdir(parents=True, exist_ok=True)
        host = escape(parsed.hostname or "")
        (RES / "xml/panel_network.xml").write_text(
            '<network-security-config><domain-config cleartextTrafficPermitted="false">'
            f'<domain includeSubdomains="true">{host}</domain>'
            '<trust-anchors><certificates src="system"/></trust-anchors>'
            '</domain-config></network-security-config>'
        )
        (RES / "values/panel.xml").write_text(
            f'<resources><string name="panel_origin">{escape(origin)}</string><string name="panel_mode">cloud</string></resources>'
        )
        return
    token = os.environ.get(token_env, "").strip()
    if not 40 <= len(token) <= 100:
        raise ValueError(f"Defina uma credencial de 40 a 100 caracteres em ${token_env} antes de provisionar.")
    _write_device_config(origin, token, "cloud")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "provision", "prepare-cloud", "provision-cloud"])
    parser.add_argument("--origin", help="Origem HTTPS pública do Jarvis na Railway")
    parser.add_argument("--token-env", default="JARVIS_CONTROL_TOKEN", help="Variável local que contém a credencial do aparelho")
    args = parser.parse_args()
    if args.action in {"prepare", "provision"}:
        provision(args.action)
    else:
        cloud(args.action, args.origin, args.token_env)
