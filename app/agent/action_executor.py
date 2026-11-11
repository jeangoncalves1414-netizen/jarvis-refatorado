"""Action executor - executes tools with guardrails and mode filtering."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from threading import local
from typing import Any

from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core.action_proposals import build_proposal_preview
from app.core.actions import ActionRecord, ToolMetadata, arguments_digest, pending_action_broker, summarize_result, executing_action
from app.storage.action_store import ActionStore, action_store
from app.storage.auto_approvals import auto_approvals
from app.core.runs import RunCancelled, current_origin, current_run
from app.agent import effect_checks
from app.core.capability_health import record_tool_result


LegacyExecute = Callable[[str, dict, str], ToolResult]


class ActionExecutor:
    """Executes tool actions with guardrails and mode-based filtering."""
    
    def __init__(
        self,
        allowed_tool_names: frozenset[str] | None,
        guardrails: ToolCallGuardrailController,
        legacy_execute: LegacyExecute,
        metadata_for: Callable[[str], ToolMetadata | None] | None = None,
        store: ActionStore | None = None,
        source: str = "conversation",
    ) -> None:
        self.allowed_tool_names = allowed_tool_names
        self.guardrails = guardrails
        self.legacy_execute = legacy_execute
        self.metadata_for = metadata_for or (lambda _name: None)
        context = current_run.get()
        self.store = store or (context[0] if context else action_store)
        self.run_id = context[1] if context and self.store is context[0] else None
        origin = current_origin.get()
        self.source = source if origin == "chat" else f"{origin}:{source}"
        # The approval worker must not overwrite what the planner just proposed.
        self._thread = local()
        self._last_open = None
        self._completed_writes = {}
        from app.core.ui_events import current_popup_session
        from app.core.model_routing import current_model_mode
        self.session_id = current_popup_session.get()
        self.model_mode = current_model_mode.get()

    @property
    def last_action(self) -> ActionRecord | None:
        return getattr(self._thread, "last_action", None)

    @last_action.setter
    def last_action(self, value: ActionRecord | None) -> None:
        self._thread.last_action = value

    def propose(self, name: str, args: dict[str, Any] | None, *, user_text: str | None = None) -> ActionRecord:
        metadata = self.metadata_for(name) or ToolMetadata(
            capabilities=(name,), default_risk="high", requires_confirmation=True,
        )
        # Alvo, mudança, reversibilidade e escopo (C1); valores sensíveis dos argumentos não entram.
        preview = build_proposal_preview(name, args, metadata)
        proposal = ActionRecord.create(
            source=self.source, tool_name=name, metadata=metadata, arguments=args or {}, preview=preview,
        )
        proposal.run_id = self.run_id
        if proposal.status == "awaiting_confirmation" and user_text is not None:
            pending_action_broker.register(proposal.id, lambda: self.execute_authorized(proposal.id, name, args, user_text))
        try:
            action = self.store.create(proposal)
        except BaseException:
            pending_action_broker.discard(proposal.id)
            raise
        if action.status == "awaiting_confirmation":
            action = self._auto_approve(action, name, args or {}, metadata)
        self.last_action = action
        if action.status == "awaiting_confirmation":
            from app.agent.tool_activity import emit_activity
            emit_activity(action, self.session_id)
        return action

    def _auto_approve(self, action: ActionRecord, name: str, args: dict[str, Any], metadata: ToolMetadata) -> ActionRecord:
        """Modo liberado ou regra ativa aprovam sem perguntar; o motivo e a origem ficam na Central."""
        operation, target = metadata.operation_for(args), metadata.target_for(args)
        if auto_approvals.liberated():
            reason = f"Aprovada pelo modo liberado (origem: {self.source})."
        else:
            rule = auto_approvals.match(name, operation, target, risk=action.risk, digest=action.arguments_digest)
            if rule is None:
                auto_approvals.remember_scope(action.id, name, operation, target, action.risk, action.arguments_digest)
                return action
            reason = f"Auto-aprovada pela regra {rule['id']} ({rule['label']}; origem: {self.source})."
        try:
            approved = self.store.transition(action.id, "authorized", result_summary=reason, expected_status="awaiting_confirmation")
        finally:
            pending_action_broker.discard(action.id)
        return approved

    def execute(self, name: str, args: dict | None, user_text: str) -> str:
        self.last_action = None
        if self.run_id:
            self.store.check_cancelled(self.run_id)
        args = deepcopy(args or {})
        from app.agent.loop_policy import is_action_discussion
        if is_action_discussion(user_text):
            return "O usuário pediu uma explicação sobre ações anteriores, não uma nova execução. Responda usando os recibos do histórico."
        
        # Filter by allowed tools
        if self.allowed_tool_names is not None and name not in self.allowed_tool_names:
            return f"Ferramenta bloqueada pelo modo atual: {name}."
        # Fase contexto 2: memórias com fonte preenchem parâmetros vazios (sem chamada ao modelo).
        from app.agent.memory_params import apply_memory_params
        args = apply_memory_params(name, args, user_text)
        if name == 'personal_records' and args.get('kind') == 'finance' and args.get('action') == 'update':
            import re
            from app.agent.loop_policy import normalize
            request = normalize(user_text)
            fields = args.get('fields') or {}
            if re.search(r'\b(?:somente|apenas|so)\b.*\bvalor\b', request):
                args['fields'] = {k: v for k, v in fields.items() if k == 'amount'}
            elif re.search(r'\b(?:foi (?:no|na)|corrij\w* a conta)\b', request) and not re.search(r'\d|r\$', request):
                args['fields'] = {k: v for k, v in fields.items() if k == 'account'}
        if name in {'task_tool', 'habit_tool', 'finance_tool', 'checklist_tool', 'personal_records'} and args.get('action') in {'delete', 'delete_list'}:
            import re
            from app.agent.loop_policy import normalize
            if re.search(r'\b(?:tod[oa]s|em massa|em lote)\b', normalize(user_text)):
                return 'Exclusão ampla: use personal_records action=preview e peça a confirmação dos registros na tela Hoje. Nenhum registro foi excluído.'
        if name == "checklist_tool" and args.get("action") == "create_list" and not (args.get("items") or args.get("text")):
            import re
            from app.agent.loop_policy import normalize
            if re.search(r"\b(?:com\s+(?!(?:titulo|nome)\b)|contendo\s+|itens\s*:)", normalize(user_text)):
                return "A lista não foi criada: o pedido inclui itens. Envie-os em text ou items na mesma chamada create_list."
        if name == "finance_tool" and args.get("action") == "update" and "amount" in args:
            import re
            from app.agent.loop_policy import normalize
            request = normalize(user_text)
            # An explicit amount-only correction cannot rewrite copied model defaults.
            if re.search(r"\b(?:somente|apenas|so)\b", request) and re.search(r"r\$|\bvalor\b", request) and not re.search(r"\b(?:categoria|descricao|data|tipo)\b", request):
                args = {key: value for key, value in args.items() if key in {"action", "trans_id", "amount", "match_description"}}

        write_key = self._write_key(name, args)
        if write_key in self._completed_writes:
            self.last_action, message = self._completed_writes[write_key]
            return message

        key = self._opening_key(name, args, user_text)
        if key and self._last_open and self._last_open[0] == key:
            _, self.last_action, message = self._last_open
            return f"Esta abertura já foi confirmada neste pedido; não foi repetida. {message}"
        self._last_open = None

        action = self.propose(name, args, user_text=user_text)
        if action.status == "awaiting_confirmation":
            return (
                f"Ação proposta ({action.id}): {action.preview} "
                "Ela exige confirmação no painel antes de ser executada."
            )

        return self._execute(action, name, args, user_text)

    @staticmethod
    def _write_key(name, args):
        if name == 'personal_records' and args.get('action') == 'undo':
            # Rephrasing "last" must not advance to the previous receipt again.
            return name, 'undo', str(args.get('receipt_id') or 'last')
        if name == 'vault_save_note':
            return name, 'create', arguments_digest({'title': str(args.get('title') or '').strip(), 'folder': args.get('folder') or '05-Notas'})
        if name == 'personal_records' and args.get('kind') == 'note' and args.get('action') == 'create':
            return ActionExecutor._write_key('vault_save_note', args.get('fields') or {})
        if name == 'personal_records' and args.get('action') == 'delete' and args.get('record_id') and args.get('kind') in {'finance', 'task', 'habit'}:
            kind = args['kind']
            tool = {'finance': 'finance_tool', 'task': 'task_tool', 'habit': 'habit_tool'}[kind]
            field = {'finance': 'trans_id', 'task': 'task_id', 'habit': 'habit_id'}[kind]
            return ActionExecutor._write_key(tool, {'action': 'delete', field: args['record_id']})
        if name == 'personal_records' and args.get('action') == 'create' and args.get('kind') in {'finance', 'task', 'habit'}:
            fields = dict(args.get('fields') or {})
            kind = args['kind']
            if kind == 'habit':
                fields['name'] = fields.pop('title', fields.get('name', ''))
            return ActionExecutor._write_key({'finance': 'finance_tool', 'task': 'task_tool', 'habit': 'habit_tool'}[kind],
                                            {**fields, 'action': 'add' if kind == 'finance' else 'create'})
        operations = {
            "personal_records": {"create", "update", "delete", "complete", "reopen", "pause", "resume", "progress", "refund", "pay", "start", "undo", "to_task", "preferences_set"},
            "task_tool": {"create", "create_many", "delete"},
            "habit_tool": {"create", "create_many", "delete"},
            "finance_tool": {"add", "add_many", "delete"},
            "checklist_tool": {"create_list", "add_items", "delete_list", "delete_item"},
        }
        if args.get("action") in operations.get(name, set()):
            canonical = args
            try:
                if name == "finance_tool" and args["action"] == "add":
                    from app.services.finance import FinanceService
                    kind = "income" if str(args.get("type") or "").lower() in {"income", "receita", "ganho"} else "expense"
                    canonical = FinanceService.normalize_entry(kind, args.get("amount"), args.get("category"), args.get("description"), args.get("date"))
                    canonical['account'] = str(args.get('account') or '').strip()
                    canonical['installments'] = args.get('installments', 1)
                elif name == "task_tool" and args["action"] == "create":
                    from app.agent.tools.lifestyle_tools import _prepare_task
                    canonical = _prepare_task({**args, "priority": args.get("priority") or 3})
                elif name == "habit_tool" and args["action"] == "create":
                    from app.agent.tools.lifestyle_tools import _prepare_habit
                    canonical = _prepare_habit(args)
            except (TypeError, ValueError):
                # Invalid arguments still reach the tool's normal validation.
                pass
            return name, args["action"], arguments_digest(canonical)
        return None

    @staticmethod
    def _opening_key(name, args, user_text):
        import re
        from urllib.parse import urlsplit
        from app.agent.loop_policy import normalize
        if name != "web_search" or args.get("action") != "open_url":
            return None
        if re.search(r"\b(?:novamente|de novo|outra vez|(?:duas|tres|\d+) vezes)\b", normalize(user_text)):
            return None
        try:
            url = urlsplit(str(args.get("query") or args.get("url") or ""))
            if url.scheme not in {"http", "https"} or not url.hostname:
                return None
            return (url.scheme, url.hostname.lower().removeprefix("www."), url.port, url.path or "/", url.query, url.fragment)
        except ValueError:
            return None

    def execute_authorized(self, action_id: str, name: str, args: dict, user_text: str) -> str:
        """Run a once-approved action kept only in this process's memory."""
        action = self.store.get(action_id)
        if not action or action.status != "authorized":
            raise ValueError("Ação não está autorizada ou expirou.")
        if action.tool_name != name or action.arguments_digest != arguments_digest(args):
            raise ValueError("Os parâmetros não correspondem à proposta autorizada.")
        return self._execute(action, name, args, user_text)

    def _execute(self, action: ActionRecord, name: str, args: dict, user_text: str) -> str:
        from app.agent.tool_activity import current_activity, emit_activity, record_memory_lookup
        action_id = action.id
        before = self.guardrails.before_call(name, args)
        if not before.allow:
            self.last_action = self.store.transition(action_id, "cancelled", result_summary=before.message, expected_status=action.status)
            emit_activity(self.last_action, self.session_id)
            return before.message
        self.last_action = self.store.transition(action_id, "running", expected_status=action.status)
        emit_activity(self.last_action, self.session_id, args=args)
        before_effect = None
        try:
            before_effect = effect_checks.capture_before(name, args)
        except Exception:
            pass
        try:
            token = executing_action.set((name, action.arguments_digest))
            activity_token = current_activity.set((self.last_action, self.session_id))
            try:
                from app.services import personal_history
                result = personal_history.execute(name, args, lambda: self.legacy_execute(name, args, user_text), session=self.session_id or '', operation_id=action_id)
            finally:
                current_activity.reset(activity_token)
                executing_action.reset(token)
            if not isinstance(result, ToolResult) or type(result.ok) is not bool or not isinstance(result.message, str):
                result = ToolResult(False, "A ferramenta retornou um resultado inválido; conclusão não confirmada.")
        except RunCancelled:
            # "Parar pedido" no meio da etapa (ex.: espera): a ação fica cancelada, não com falha.
            self.last_action = self.store.transition(action_id, "cancelled", result_summary="Pedido cancelado durante a execução.")
            emit_activity(self.last_action, self.session_id, args=args)
            raise
        except Exception:
            self.last_action = self.store.transition(action_id, "failed", result_summary="A ferramenta lançou uma exceção; conclusão não confirmada.")
            emit_activity(self.last_action, self.session_id, args=args)
            record_tool_result(name, False, "A ferramenta lançou uma exceção.")
            raise
        after = self.guardrails.after_call(name, args, result.message)
        message = result.message if after.allow else after.message
        succeeded = result.ok and after.allow
        effect = effect_checks.NOT_APPLICABLE
        if succeeded:
            # Efeito visível (abrir app, tocar mídia, abrir link): confirma por regra ou avisa que não deu.
            # Falha da sonda significa efeito desconhecido, nunca confirmado.
            try:
                effect = effect_checks.check_effect(name, args, result, before_effect)
            except RunCancelled:
                self.last_action = self.store.transition(action_id, "cancelled", result_summary="Cancelado durante a verificação; efeito não confirmado.", effect_status="unconfirmed")
                emit_activity(self.last_action, self.session_id, args=args)
                raise
            except Exception:
                effect = effect_checks.EffectCheck("unconfirmed", "a verificação do efeito falhou")
            if effect.status != "not_applicable":
                if not isinstance(result.data, dict):
                    result.data = {}
                result.data["effect"] = effect.as_dict()
                if effect.status == "unconfirmed" and name != "media_tool":
                    message = "A ferramenta retornou sem erro; o efeito ainda não foi verificado."
                message = f"{message} {effect.text()}".strip()
        result.message = message
        result.ok = bool(succeeded)
        self.last_action = self.store.transition(action_id, "succeeded" if succeeded else "failed", result_summary=summarize_result(message, args), effect_status=effect.status, effect_evidence=summarize_result(effect.evidence, args))
        if not isinstance(result.data, dict):
            result.data = {}
        result.data["receipt"] = self.last_action.public_dict()
        emit_activity(self.last_action, self.session_id, result.data, args=args)
        if name != "memory_tool" or args.get("action", "search") in {"search", "recall", "retrieve", "query"}:
            record_memory_lookup(name, result)
        # O1: o resultado real alimenta a saúde da integração na página Integrações.
        record_tool_result(name, succeeded, None if succeeded else summarize_result(message, args))
        if succeeded:
            write_key = self._write_key(name, args)
            if write_key:
                # A create after a delete is a new operation; a repeated delete is not.
                for cached in list(self._completed_writes):
                    if cached[0] == write_key[0] and cached[1] != write_key[1]:
                        del self._completed_writes[cached]
                self._completed_writes[write_key] = (self.last_action, result.model_observation())
            key = self._opening_key(name, args, user_text)
            if key and effect.status == "confirmed":
                self._last_open = (key, self.last_action, message)
            # Popups do painel (lote 6): pedido explícito ou automático; nunca derruba a ação.
            try:
                from app.core.ui_events import publish_personal_change
                from app.agent.popups import after_tool_success
                publish_personal_change(name, args)
                after_tool_success(name, args, result)
            except Exception:
                pass
        return message
