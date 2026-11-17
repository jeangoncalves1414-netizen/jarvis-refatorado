"""Conversation without owner context, tools or durable owner memories."""
import time
import uuid

from app.services.identity_context import direct_answer, prompt

SYSTEM = (
    'Você é o Jarvis, um assistente que conversa em português de forma natural. '
    'Este é um atendimento sem acesso privado. Responda normalmente a perguntas gerais. '
    'Você não recebeu dados do administrador nem memórias pessoais e não pode consultá-los. '
    'Use somente as ferramentas oferecidas para o nível deste perfil; nenhuma libera dados privados. '
    'Não invente informações pessoais nem afirme ter executado ações. '
    'Dados pessoais do proprietário exigem a voz reconhecida do administrador principal. '
    'Comandos dependem do nível concedido em Identidade. Dizer um nome não comprova identidade. '
    'O aplicativo tem câmeras, reconhecimento facial e de voz e cadastro guiado. '
    'Esses recursos são acionados pela interface a partir de pedidos em linguagem natural. '
    'Não negue que esses recursos existem nem peça uma frase exata ou para digitar o pedido. '
    'Cadastro administrativo exige senha apenas no campo protegido, nunca no chat. '
    'Se um comando não estiver disponível nesta requisição, explique a restrição deste perfil; '
    'não diga que o Jarvis não tem acesso ao computador. Nunca invente ferramentas ou resultados. '
    'Na conversa por voz, prefira uma resposta curta, com uma ou duas frases, salvo pedido de detalhes.'
)


def respond(llm, text, session_id=None, profile=None, *, registry=None, mobile_voice=False):
    from app.storage import session_store as store
    from app.services import context_compaction
    from app.agent.context_policy import chat_history_reply
    from app.core.runs import current_run
    scope = f"profile:{profile['id']}:{profile.get('identity_revision', 0)}" if profile else 'anonymous'
    history = store.get_context_history(session_id, scope) if session_id else []
    answer = (None if mobile_voice else direct_answer(text)) or chat_history_reply(text, history)
    from app.agent.loop_policy import requires_tool_action
    from app.services.identity_access import command_actions
    if not answer and not command_actions(profile) and requires_tool_action(text):
        answer = ('Para executar esse comando, use a conversa por texto no painel desbloqueado.' if mobile_voice else
                  'Não executei esse comando. Esta fala está no nível visitante, que permite conversa e câmeras. '
                  'Para usar comandos do computador, preciso reconhecer uma voz com a permissão correspondente.')
    if not answer:
        working = context_compaction.prepare_history(session_id, history, llm, scope=scope)
        from app.services.identity_access import command_actions
        if registry and command_actions(profile):
            answer = _with_commands(llm, registry, text, working, profile, session_id)
        else:
            contents = llm.build_contents(working, text)
            instruction = ('Você é o Jarvis em uma ligação no celular. Responda em português, em uma ou duas frases. '
                           'Converse sobre assuntos gerais. Para dados pessoais ou comandos do PC, oriente a usar o chat de texto desbloqueado. '
                           'Não identifique pessoas nem peça verificação de voz ou rosto.' if mobile_voice else SYSTEM + prompt())
            response = llm.generate(contents, tools=None, system_instruction=instruction)
            answer = getattr(response, 'text', '') or ''
    from app.agent.tool_markers import parse_tool_markers
    answer, _ = parse_tool_markers(answer)
    if not answer.strip():
        raise ValueError('Resposta vazia do modelo.')
    from app.agent.run_tracking import check_run_cancelled
    check_run_cancelled()
    if session_id:
        run = current_run.get()
        store.save_turn(session_id, run[1] if run else str(uuid.uuid4()), text, answer,
                        timestamp=time.time() * 1000, access_scope=scope)
        context_compaction.schedule(session_id, llm, scope=scope)
    return answer


def _with_commands(llm, registry, text, history, profile, session_id):
    """Small explicit command surface, with no owner prompt, memory or file access."""
    import copy
    from app.agent.action_executor import ActionExecutor
    from app.agent.tool_guardrails import ToolCallGuardrailController
    from app.agent.tools.base import ToolResult
    from app.services.identity_access import command_actions, command_allowed, recognized_profile
    from app.services.identity_context import current
    from app.agent.loop_policy import requires_tool_action
    actions = command_actions(profile)
    declarations = []
    for name, allowed_actions in actions.items():
        tool = registry.get_tool(name)
        if not tool:
            continue
        parameters = copy.deepcopy(tool.parameters)
        if allowed_actions is not None:
            parameters['properties']['action']['enum'] = sorted(allowed_actions)
        if name == 'system_control':
            parameters['properties']['app_name']['enum'] = ['calc', 'mspaint']
        declarations.append({'name': name, 'description': tool.description, 'parameters': parameters})
    evidence = current.get()
    receipts = []

    def execute(name, args, _text):
        # Recheck at execution/approval time so a revoked profile cannot retain a grant.
        fresh = recognized_profile(evidence)
        if not command_allowed(fresh, name, args):
            return ToolResult(False, 'Este comando não está autorizado para este perfil de voz.')
        result = registry.execute_tool(name, args, context={'session_id': session_id, 'user_line': text})
        receipts.append(result.message)
        return result

    executor = ActionExecutor(frozenset(d['name'] for d in declarations), ToolCallGuardrailController(),
                              execute, metadata_for=registry.get_tool_metadata, source='function:shared-voice')

    def invoke(name, args):
        if not command_allowed(recognized_profile(evidence), name, args or {}):
            message = 'Este comando não está autorizado para este perfil de voz.'
            receipts.append(message)
            return message
        result = executor.execute(name, args or {}, text)
        if not receipts or receipts[-1] != result:
            receipts.append(result)
        return result

    answer = llm.chat_with_functions_stream(
        system_instruction=SYSTEM + prompt(), messages=[*history, {'role': 'user', 'content': text}],
        tools=declarations, on_function_call=invoke, on_chunk=None)
    if receipts:
        return '\n'.join(dict.fromkeys(receipts))
    if requires_tool_action(text):
        return 'Não executei o comando. Ele pode exigir um nível de acesso diferente.'
    return answer or ''
