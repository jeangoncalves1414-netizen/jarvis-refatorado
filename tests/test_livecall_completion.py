from app.agent.loop_policy import missing_requested_steps, should_use_agent_loop, is_action_discussion


def receipt(name, **args):
    return {'name': name, 'args': args, 'status': 'succeeded'}


REQUEST = 'Olá quero que você abra um link do YouTube, aguarde 10 segundos e abra o Spotify'


def test_spoken_request_uses_ordered_loop():
    assert should_use_agent_loop(REQUEST, 'general', {'mode': 'auto'})[0]
    assert should_use_agent_loop('depois de aguardar 10 segundos quero que você abra uma música do Spotify', 'general', {'mode': 'auto'})[0]


def test_search_does_not_complete_open_or_wait():
    assert missing_requested_steps(REQUEST, [receipt('web_search', query='youtube spotify')]) == ['abrir youtube', 'esperar 10 segundos', 'abrir spotify']


def test_complete_media_sequence_and_visible_url():
    steps = [receipt('web_search', action='open_url', query='https://www.youtube.com/watch?v=abc'), receipt('wait', seconds=10), receipt('spotify', action='open')]
    assert missing_requested_steps(REQUEST, steps) == []
    assert missing_requested_steps(REQUEST, [steps[1], steps[0], steps[2]]) == ['esperar 10 segundos']
    steps[2]['status'] = 'failed'
    assert missing_requested_steps(REQUEST, steps) == ['abrir spotify']


def test_questions_and_research_do_not_require_opening():
    assert missing_requested_steps('Como abrir o Spotify?', []) == []
    assert missing_requested_steps('Pesquise vídeos no YouTube', []) == []
    assert missing_requested_steps('Abra o YouTube', [receipt('browser', action='navigate', url='https://example.com/youtube')]) == ['abrir youtube']
    assert missing_requested_steps('Abra o Spotify', [receipt('open_windows_app', action='status', app_name='spotify')]) == ['abrir spotify']


def test_spoken_parallel_request_keeps_both_actions_and_requires_spotify():
    request = 'tá quero que você abra o navegador no roblox.com e ao mesmo tempo abrir Spotify'
    assert should_use_agent_loop(request, 'general', {'mode': 'auto'})[0]
    steps = [receipt('web_search', action='open_url', query='https://roblox.com')]
    assert missing_requested_steps(request, steps) == ['abrir spotify']
    assert missing_requested_steps(request, [*steps, receipt('spotify', action='open')]) == []
    assert missing_requested_steps(request, [receipt('spotify', action='open'), *steps]) == []
    assert missing_requested_steps(request, [receipt('spotify', action='open')]) == ['abrir roblox']
    assert missing_requested_steps('Abra example.org no navegador', []) == ['abrir example.org']


def test_spoken_wait_reference_is_one_pause_but_two_commands_remain_two():
    request = 'Olá quero que você abra google.com no navegador e depois Abra o Spotify e ele aguarde 10 segundos e depois de 10 segundos Você fecha o Spotify'
    steps = [receipt('browser', action='navigate', url='https://google.com'), receipt('spotify', action='open'), receipt('wait', seconds=10), receipt('open_windows_app', action='close', app_name='Spotify')]
    assert missing_requested_steps(request, steps) == []
    assert missing_requested_steps('Abra Spotify, aguarde 10 segundos e aguarde 10 segundos', steps[:3]) == ['esperar 10 segundos']
    assert missing_requested_steps('Abra Spotify, aguarde 10 segundos, abra YouTube e depois de 10 segundos feche Spotify', steps[:3]) == ['abrir youtube', 'esperar 10 segundos']


def test_complaint_is_not_a_new_command_but_explicit_followup_is():
    assert is_action_discussion('o que está acontecendo por que você está abrindo Box três vezes')
    assert is_action_discussion('Quais foram as últimas três coisas que você fez')
    assert not is_action_discussion('Pode abrir o Roblox?')
    assert not is_action_discussion('Por que você abriu Roblox? Agora abra Spotify')
