"""Public activity receipts: real executions, without raw tool arguments."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import re
from contextvars import ContextVar
from app.agent import turn_meta
from app.core import ui_events

current_activity = ContextVar("current_activity", default=None)
activity_listener = ContextVar("activity_listener", default=None)


def action_description(name, args):
    """Small public labels from declared arguments, never from model narration."""
    from app.core.actions import redact
    operation = str(args.get("action", ""))
    if name == 'personal_records':
        labels = {'create': 'Registrar', 'update': 'Corrigir registro', 'delete': 'Excluir registro', 'undo': 'Desfazer alteração',
                  'list': 'Consultar registros', 'history': 'Consultar histórico', 'summary': 'Consultar o dia', 'preview': 'Preparar prévia',
                  'complete': 'Concluir registro', 'reopen': 'Reabrir registro', 'pause': 'Pausar', 'resume': 'Retomar',
                  'progress': 'Registrar progresso', 'refund': 'Registrar estorno', 'pay': 'Registrar pagamento', 'start': 'Iniciar sessão',
                  'to_task': 'Criar tarefa da anotação', 'preferences_get': 'Consultar preferências', 'preferences_set': 'Salvar preferências'}
        return {'label': labels.get(operation, 'Organização pessoal'), 'speech': 'Conferindo seus registros.', 'completion': 'Concluí a alteração solicitada.'}
    target = str(args.get("url") or args.get("query") or args.get("app_name") or "")
    # URLs in labels carry only their host; paths, credentials and queries stay private.
    target = re.sub(r"https?://[^\s]+", lambda m: _hostname(m[0]), target)
    target = redact(" ".join(target.split()), limit=160)
    site = target.removeprefix("www.").split("/")[0].lower()
    spoken = {"roblox.com": "Roblox", "youtube.com": "YouTube", "open.spotify.com": "Spotify"}.get(site, "o site")
    if (name == "web_search" and operation == "open_url") or (name == "browser" and operation in {"navigate", "open_url"}):
        return {"label": f"Abrir {target or 'site'}", "speech": f"Abrindo {spoken}.", "completion": f"Abri {spoken}."}
    if name == "web_search":
        return {"label": f"Pesquisar {target}".strip(), "speech": "Pesquisando na web.", "completion": "Concluí a pesquisa."}
    if name == "open_windows_app" and operation in {"", "open"}:
        app = target if re.fullmatch(r"[\w À-ÿ-]{1,40}", target) else "o aplicativo"
        return {"label": f"Abrir {target or 'aplicativo'}", "speech": f"Abrindo {app}.", "completion": f"Abri {app}."}
    if name == "spotify" and operation == "open":
        return {"label": "Abrir Spotify", "speech": "Abrindo Spotify.", "completion": "Abri Spotify."}
    if name == "wait":
        seconds = args.get("seconds")
        duration = f" {seconds} segundos" if isinstance(seconds, (int, float)) and 0 <= seconds <= 3600 else ""
        return {"label": f"Aguardar{duration}", "speech": f"Aguardando{duration}.", "completion": f"Aguardei{duration}."}
    if name == "file_manager":
        descriptions = {
            "create": ("Criar arquivo", "Criando o arquivo.", "Criei o arquivo solicitado."),
            "mkdir": ("Criar pasta", "Preparando a pasta.", "Preparei a pasta solicitada."),
            "read": ("Ler arquivo", "Lendo o arquivo.", "Li o arquivo solicitado."),
            "list": ("Listar arquivos", "Consultando a pasta.", "Consultei os arquivos da pasta."),
        }
        if operation in descriptions:
            label, speech, completion = descriptions[operation]
            return {"label": label, "speech": speech, "completion": completion}
    return {"label": name.replace("_", " "), "speech": "Executando a próxima ação.", "completion": "Ação concluída."}


def _hostname(value):
    try:
        return urlsplit(value).hostname or "site"
    except ValueError:
        return "site"


def report_progress(data, detail):
    active = current_activity.get()
    if active:
        action, session_id = active
        emit_activity(action, session_id, data, detail)


def public_sources(data):
    if not isinstance(data, dict):
        return []
    sources = []
    items = data.get("results") or data.get("sources") or ([data] if data.get("url") else [])
    if not isinstance(items, list):
        return []
    for item in items[:30]:
        if not isinstance(item, dict):
            continue
        try:
            url = urlsplit(str(item.get("url") or ""))
            if url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password:
                continue
            # Preserve page identifiers, but never publish credentials from URLs.
            query = urlencode([(key, value) for key, value in parse_qsl(url.query)
                               if not re.search(r"token|auth|password|secret|signature|session|api.?key|^key$", key, re.I)])
            href = urlunsplit((url.scheme, url.netloc, url.path, query, ""))
        except ValueError:
            continue
        sources.append({"url": href, "title": str(item.get("title") or url.hostname)[:200],
                        "read": item.get("read_status") == "read"})
    return sources


def emit_activity(action, session_id, data=None, detail=None, *, args=None):
    snapshot = turn_meta.snapshot().get("tool_activity", [])
    previous = next((item for item in snapshot if item["id"] == action.id), {})
    entry = {"id": action.id, "tool": action.tool_name, "status": action.status,
             "sources": public_sources(data) or previous.get("sources", [])}
    entry.update({key: previous[key] for key in ("label", "speech") if key in previous})
    if args is not None:
        description = action_description(action.tool_name, args)
        entry.update({key: description[key] for key in ("label", "speech")})
    if getattr(action, "result_summary", None):
        entry["result"] = action.result_summary
    if detail:
        entry["detail"] = detail
    entries = [item for item in snapshot if item["id"] != action.id]
    turn_meta.record("tool_activity", [*entries, entry][-100:])
    event = {"type": "tool_activity", "phase": "tool_activity", "session_id": session_id,
             "run_id": action.run_id, "activity": entry}
    if session_id:
        ui_events.publish(event)
    listener = activity_listener.get()
    if listener:
        listener(event)


def record_memory_lookup(name, result):
    if not result.ok or name not in {"vault_search", "memory_tool"}:
        return
    data = result.data if isinstance(result.data, dict) else {}
    items = data.get("results") or []
    if not isinstance(items, list):
        items = []
    # A deliberate lookup is distinct from ambient context injected every turn.
    turn_meta.record("memory_lookup", {"tool": name, "summary": result.message[:1000],
        "items": [{"title": str(item.get("file") or item.get("title") or "Memória")[:200],
                   "text": str(item.get("snippet") or item.get("text") or "")[:600]}
                  for item in items[:10] if isinstance(item, dict)]})
