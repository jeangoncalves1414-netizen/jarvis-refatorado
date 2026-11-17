"""Run with python -m scripts.mobile_wifi pair IP or python -m scripts.mobile_wifi serve."""
import argparse
import base64
import hmac
import ipaddress
import json
import os
import secrets
import ssl
import subprocess
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from scripts.sync_mobile_routine import PACKAGE, apply_change, snapshot, SyncConflict, transfer

DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Jarvis" / "routine-wifi"
PORT = 48731


def pair(address):
    ip = ipaddress.IPv4Address(address)
    if not ip.is_private or ip.is_loopback:
        raise ValueError("Use o IPv4 local do computador.")
    DIR.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Jarvis Rotina")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=1))
            .not_valid_after(now+timedelta(days=365)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip)]),False)
            .sign(key, hashes.SHA256()))
    token = secrets.token_urlsafe(32)
    phone = dict(url=f"https://{ip}:{PORT}/routine", token=token,
                 cert=base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode())
    subprocess.run(["adb","-d","exec-in","run-as",PACKAGE,"tee","files/pair.json"],
                   input=json.dumps(phone).encode(), stdout=subprocess.DEVNULL, check=True)
    transfer("pair")
    (DIR/"tls.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM)+key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (DIR/"config.json").write_text(json.dumps(dict(address=str(ip),token=token)))
    print("Aparelho pareado.")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, data):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path != "/routine" or not hmac.compare_digest(self.headers.get("Authorization",""),
                                                               "Bearer "+self.server.token):
            self.respond(403,{})
            return
        try:
            size = int(self.headers.get("Content-Length",0))
            if not 0 < size <= 1024*1024:
                self.respond(413,{})
                return
            req = json.loads(self.rfile.read(size))
            for index,change in enumerate(req["queue"]):
                try:
                    apply_change(change)
                except SyncConflict as err:
                    self.respond(409,dict(index=index,current=err.current))
                    return
            self.respond(200,snapshot(req["rev"]))
        except (ValueError,KeyError,TypeError) as err:
            self.respond(400,{"error":str(err)[:160]})


def serve():
    config = json.loads((DIR/"config.json").read_text())
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(DIR/"tls.pem")
    class Server(HTTPServer):
        def get_request(self):
            sock, addr = super().get_request()
            sock.settimeout(8)
            try:
                return tls.wrap_socket(sock,server_side=True),addr
            except Exception:
                sock.close()
                raise
    with Server((config["address"],PORT),Handler) as server:
        server.token = config["token"]
        server.serve_forever()


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action",required=True)
    sub.add_parser("pair").add_argument("address")
    sub.add_parser("serve")
    args = parser.parse_args()
    if args.action == "pair":
        pair(args.address)
    else:
        serve()

