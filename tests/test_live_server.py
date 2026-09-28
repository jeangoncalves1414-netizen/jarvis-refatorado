import pytest
import urllib.request
import urllib.error
import json

def test_all():
    base = "http://127.0.0.1:8000"
    try:
        urllib.request.urlopen(f"{base}/api/evolute/summary", timeout=1)
    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
        pytest.skip("Live server is not running at http://127.0.0.1:8000 - skipping live server test.")

    print("--- 1. Testing GET /api/evolute/summary ---")
    req = urllib.request.Request(f"{base}/api/evolute/summary")
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        print("Summary OK:", data.get("ok"))
        print("Habits count:", data.get("habits", {}).get("total"))
        print("Water current:", data.get("water", {}).get("current_ml"))
        print("Motivational speech sample:", data.get("motivational", {}).get("speech", "")[:80] + "...")
        assert data.get("ok") is True

    print("\n--- 2. Testing POST /api/evolute/water/add ---")
    payload = json.dumps({"amount_ml": 250}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/evolute/water/add",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        print("Water Add OK:", data.get("ok"))
        print("New Total ML:", data.get("total_ml"))
        assert data.get("ok") is True

    print("\n--- 3. Testing POST /api/evolute/habit/toggle ---")
    payload = json.dumps({"habit_name_or_id": "agua", "completed": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/evolute/habit/toggle",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        print("Habit Toggle OK:", data.get("ok"))
        print("Habit Title:", data.get("title"))
        assert data.get("ok") is True

    print("\n--- 4. Testing GET / (React Frontend) ---")
    req = urllib.request.Request(f"{base}/")
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200
        html = res.read().decode("utf-8")
        print("Frontend Status:", res.status, "Length:", len(html))
        assert "<!doctype html>" in html.lower() or "<html" in html.lower()

    print("\n--- 5. Testing GET /evolute ---")
    try:
        req = urllib.request.Request(f"{base}/evolute")
        with urllib.request.urlopen(req, timeout=5) as res:
            print("Evolute Route Status:", res.status)
    except Exception as e:
        print("Evolute standalone page info:", e)

    print("\n>>> ALL AUTOMATIC SERVER TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_all()
