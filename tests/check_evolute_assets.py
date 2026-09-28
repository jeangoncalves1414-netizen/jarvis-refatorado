import urllib.request

tests = [
    ("GET /evolute (HTML)", "http://127.0.0.1:8000/evolute"),
    ("GET /evolute/assets JS", "http://127.0.0.1:8000/evolute/assets/index-BeaW8c7H.js"),
    ("GET /evolute/assets CSS", "http://127.0.0.1:8000/evolute/assets/index-DtM7y0W4.css"),
    ("GET /api/sync", "http://127.0.0.1:8000/api/sync"),
]
all_ok = True
for name, url in tests:
    try:
        r = urllib.request.urlopen(url, timeout=5)
        data = r.read(80)
        ct = r.headers.get("Content-Type", "")
        print(f"[OK]   {name} => {r.status} | {ct}")
    except Exception as e:
        print(f"[FAIL] {name} => {e}")
        all_ok = False

if all_ok:
    print("\n=== Evolute serving check: ALL OK - tela preta corrigida! ===")
else:
    print("\n=== Alguns endpoints falharam. ===")
