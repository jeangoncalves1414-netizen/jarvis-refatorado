"""Keep existing manual endpoints in the same personal undo history."""
import json
from app.agent.tools.base import ToolResult
from app.services import personal_history


def journal_response(tool, path, body, callback):
    try:
        payload = json.loads(body or b'{}')
        if not isinstance(payload, dict):
            return callback()
    except (ValueError, UnicodeError):
        return callback()
    if payload.get('action', '') in personal_history.READS:
        return callback()
    response = []
    def invoke():
        answer = callback()
        response.append(answer)
        if not answer:
            return ToolResult(True, 'Nenhuma alteração.')
        status, data = answer
        return ToolResult(status < 400 and data.get('ok', True), data.get('message') or data.get('error') or 'Registro atualizado pela interface.', data)
    result = personal_history.execute(tool, {'path': path, **payload}, invoke, session='organizer')
    if not response:
        return 400, {'ok': False, 'error': result.message}
    answer = response[0]
    if answer and result.data.get('personal_receipt'):
        from app.core.ui_events import publish_personal_change
        publish_personal_change('personal_records', {})
        status, data = answer
        return status, {**data, 'personal_receipt': result.data['personal_receipt']}
    return answer
