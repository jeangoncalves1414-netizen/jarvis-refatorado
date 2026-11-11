"""Organizer API. Bulk deletions require a fresh, exact UI preview."""
import hashlib
import json
import secrets
import time
from urllib.parse import urlsplit

from app.agent.tools.base import ToolResult
from app.services import personal_history as journal, personal_records as records

_previews = {}


def handle_personal_get(parts, handler):
    if parts != ['api', 'personal']:
        return None
    try:
        return 200, {'ok': True, **records.today()}
    except (ValueError, OSError) as exc:
        return 500, {'ok': False, 'error': str(exc)}


def handle_personal_post(path, body, handler):
    if urlsplit(path).path != '/api/personal':
        return None
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError('Pedido inválido.')
        operation_id = payload.pop('operation_id', None)
        if operation_id is not None and (not isinstance(operation_id, str) or not 8 <= len(operation_id) <= 100):
            raise ValueError('Identificador de operação inválido.')
        action = payload.get('action')
        with journal.LOCK:
            if action == 'bulk_preview':
                kind = payload.get('kind', '')
                rows = records.records(kind, payload.get('query', ''))
                token = secrets.token_urlsafe(24)
                now = time.time()
                for key in list(_previews):
                    if _previews[key]['expires'] < now:
                        del _previews[key]
                _previews[token] = dict(kind=kind, query=payload.get('query', ''), rows=rows, expires=now + 600)
                return 200, dict(ok=True, token=token, results=rows, message=f'Excluir {len(rows)} registro(s)? Revise os títulos antes de confirmar.')
            if action == 'bulk_confirm':
                preview = _previews.pop(payload.get('token', ''), None)
                if not preview or preview['expires'] < time.time():
                    raise ValueError('Prévia expirada. Revise novamente.')
                if records.records(preview['kind'], preview['query']) != preview['rows']:
                    raise ValueError('Os registros mudaram. Gere uma nova prévia.')
                def apply():
                    results = []
                    for target in preview['rows']:
                        result = records.mutate(preview['kind'], 'delete', {}, target)
                        results.append({'id': target['id'], 'ok': result.ok, 'message': result.message})
                        if not result.ok:
                            break
                    return ToolResult(all(r['ok'] for r in results), f"{sum(r['ok'] for r in results)} registro(s) excluído(s).", {'results': results})
                result = journal.execute('personal_records', payload, apply, session='organizer', operation_id=operation_id)
            else:
                if set(payload) - {'action', 'kind', 'record_id', 'query', 'fields', 'receipt_id'}:
                    raise ValueError('Campos de pedido desconhecidos.')
                result = journal.execute('personal_records', payload, lambda: records.dispatch(**payload, session='organizer'), session='organizer', operation_id=operation_id)
        from app.core.ui_events import publish_personal_change
        publish_personal_change('personal_records', payload)
        return (200 if result.ok else 400), {'ok': result.ok, 'message': result.message, **result.data}
    except (ValueError, TypeError, OSError, KeyError) as exc:
        return 400, {'ok': False, 'error': str(exc)}
