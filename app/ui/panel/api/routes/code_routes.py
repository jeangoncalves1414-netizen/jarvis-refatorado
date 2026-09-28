"""
Code Domain REST Endpoints (Deobfuscator, Sandbox, Snapshots, Code Review, AutoHealer)
"""
from __future__ import annotations

import json
from typing import Any, Callable


def handle_code_routes(path: str, body: bytes, send_json_fn: Callable[[int, dict[str, Any]], None]) -> bool:
    """Processa requisições REST para o domínio de Código e Ferramentas de Dev."""
    if path == "/api/deobfuscate/multi":
        try:
            from app.services.multi_deobfuscator import MultiDeobfuscatorEngine
            payload = json.loads(body.decode("utf-8") or "{}")
            code_data = payload.get("code") or payload.get("payload") or ""
            engine = MultiDeobfuscatorEngine()
            res = engine.auto_deobfuscate(code_data)
            send_json_fn(200 if res.ok else 400, res.to_dict())
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/sandbox/run":
        try:
            from app.services.sandbox_runner import SandboxRunner
            payload = json.loads(body.decode("utf-8") or "{}")
            cmd = str(payload.get("command") or payload.get("cmd") or "").strip()
            timeout = float(payload.get("timeout", 30.0))
            runner = SandboxRunner(default_timeout_s=timeout)
            res = runner.run(cmd)
            send_json_fn(200 if res.ok else 400, res.to_dict())
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/snapshot/list":
        try:
            from app.services.code_snapshots import snapshot_manager
            payload = json.loads(body.decode("utf-8") or "{}")
            filepath = str(payload.get("filepath") or "").strip()
            snaps = snapshot_manager.list_snapshots(filepath)
            send_json_fn(200, {"ok": True, "snapshots": snaps, "count": len(snaps)})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/snapshot/rollback":
        try:
            from app.services.code_snapshots import snapshot_manager
            payload = json.loads(body.decode("utf-8") or "{}")
            filepath = str(payload.get("filepath") or "").strip()
            v_id = payload.get("version_id")
            ok, msg = snapshot_manager.rollback(filepath, version_id=v_id)
            send_json_fn(200 if ok else 400, {"ok": ok, "message": msg})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/code/review":
        try:
            from app.services.code_reviewer import CodeReviewPipeline
            payload = json.loads(body.decode("utf-8") or "{}")
            code_text = str(payload.get("code") or "")
            lang = str(payload.get("language") or "python")
            pipeline = CodeReviewPipeline(max_iterations=2)
            syn_ok, syn_msg = pipeline.check_syntax(code_text, language=lang)
            send_json_fn(200 if syn_ok else 400, {"ok": syn_ok, "message": syn_msg})
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    if path == "/api/code/heal":
        try:
            from app.services.terminal_healer import TerminalAutoHealer
            payload = json.loads(body.decode("utf-8") or "{}")
            cmd = str(payload.get("command") or payload.get("cmd") or "").strip()
            err = str(payload.get("error_output") or payload.get("error") or "").strip()
            healer = TerminalAutoHealer()
            proposal = healer.diagnose_and_fix(cmd, err)
            send_json_fn(200 if proposal.ok else 400, proposal.to_dict())
        except Exception as exc:
            send_json_fn(500, {"ok": False, "error": str(exc)})
        return True

    return False
