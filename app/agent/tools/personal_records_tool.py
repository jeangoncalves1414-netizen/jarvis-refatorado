"""One consistent interface for organizer operations and contextual corrections."""
from app.agent.tools.base import BaseTool, ToolResult
from app.core.actions import ToolMetadata


class PersonalRecordsTool(BaseTool):
    name = 'personal_records'
    description = (
        'Organização pessoal. Vários hábitos = UMA chamada create kind=habit com fields.habits (lista). '
        'Histórico e desfazer persistente; corrigir o último com record_id=last; '
        'CRUD de hábitos, tarefas, finanças, notas, treinos, planos, sono e humor. '
        'Use para contas, parcelas, estorno, transferências, recorrências e preferências.'
    )

    @property
    def metadata(self):
        reads = ('list', 'summary', 'history', 'preview', 'preferences_get')
        writes = ('create', 'update', 'complete', 'reopen', 'pause', 'resume', 'progress', 'refund', 'to_task', 'pay', 'start', 'undo', 'preferences_set')
        return ToolMetadata(capabilities=('personal_records',), default_risk='critical', reversible=True,
                            operation_arguments=('action',), default_operation='list',
                            operation_risks=tuple((a, 'observe') for a in reads) + tuple((a, 'low') for a in writes) + (('delete', 'high'),),
                            target_arguments=('record_id', 'query'), default_target='seus registros pessoais',
                            effect='Consulta ou altera os registros pessoais solicitados.',
                            reversibility='Desfazer no histórico, desde que não haja uma edição posterior.', scope='Dados locais da organização pessoal.')

    @property
    def parameters(self):
        return {'type': 'object', 'properties': {
            'action': {'type': 'string', 'enum': ['list', 'summary', 'create', 'update', 'delete', 'complete', 'reopen', 'pause', 'resume', 'progress', 'refund', 'to_task', 'pay', 'start', 'history', 'undo', 'preview', 'preferences_get', 'preferences_set']},
            'kind': {'type': 'string', 'enum': ['habit', 'task', 'finance', 'note', 'workout', 'workout_plan', 'sleep', 'mood', 'personal', 'checklist', 'rule', 'recurrence', 'transfer']},
            'record_id': {'type': 'string', 'description': 'ID obtido por list; last = último registro deste tipo alterado nesta conversa.'},
            'query': {'type': 'string', 'description': 'Busca; nas alterações, título exato. Havendo ambiguidade, pergunte.'},
            'receipt_id': {'type': 'string', 'description': 'undo: ID do histórico; omita para desfazer a última alteração desta conversa.'},
            'fields': {'type': 'object', 'description': 'Hábito: habits=[{name,category,routine_block,days_of_week,start_time,target_value,unit}] para lote; ou title,start_time,days_of_week,routine_block,target_value,unit,items_list para 1. Tarefa: title,priority(1-4),project,due_date,subtasks. Finance: type,amount,category,description,date,account. Treino: exercises[{name,sets,reps,weight,minutes}]. Sono: hours. Humor: score(1-5).'},
        }, 'required': ['action']}

    def execute(self, args, context=None):
        from app.core.ui_events import current_popup_session
        from app.services import personal_history, personal_records
        session = current_popup_session.get() or (context or {}).get('session_id') or ''
        try:
            return personal_history.execute(self.name, args, lambda: personal_records.dispatch(**args, session=session), session=session)
        except (ValueError, TypeError, OSError) as exc:
            return ToolResult(False, str(exc))
