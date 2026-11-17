"""Access decisions from fresh server-issued evidence, never a client profile id."""
from app.services import identity


def recognized_profile(evidence):
    if not evidence or evidence.get('speaker_state') != 'recognized':
        return None
    try:
        profiles = identity._read().get('profiles', [])
    except ValueError:
        return None
    return next((p for p in profiles
                 if p.get('id') == evidence.get('profile_id') and
                 p.get('identity_revision', 0) == evidence.get('identity_revision', 0)), None)


def access(evidence, *, origin=None):
    # The unlocked text interface belongs to the owner. Voice is shared.
    if origin == 'chat':
        return True, None
    if origin == 'voice' and (evidence or {}).get('method') != 'voice':
        return False, None
    try:
        profiles = identity._read().get('profiles', [])
    except ValueError:
        return False, None
    if not any(p.get('role') == 'admin' for p in profiles):
        return (origin != 'voice' and not identity.IDENTITY_FILE.exists()), None
    profile = recognized_profile(evidence)
    allowed = bool(profile and profile.get('role') == 'admin'
                   and (evidence or {}).get('method') == 'voice')
    return allowed, profile


def command_level(profile):
    if not profile or profile.get('role') == 'admin':
        return 'visitor'
    level = profile.get('command_level', 'visitor')
    return level if level in {'visitor', 'user', 'delegate'} else 'visitor'


def command_actions(profile):
    level = command_level(profile)
    if level == 'visitor':
        return {}
    actions = {
        'timer': {'set_timer', 'set_alarm'}, 'wait': None,
        'realtime': {'get_weather', 'get_news', 'get_finance', 'get_holidays'},
        'system_control': {'media_play_pause', 'media_next', 'media_prev',
                           'volume_up', 'volume_down', 'volume_mute'},
    }
    if level == 'delegate':
        actions['system_control'] |= {'telemetry', 'get_brightness', 'set_brightness', 'lock_screen', 'open_app'}
    return actions


def command_allowed(profile, name, args):
    actions = command_actions(profile)
    if name not in actions:
        return False
    if actions[name] is not None and args.get('action') not in actions[name]:
        return False
    if name == 'system_control' and args.get('action') == 'open_app':
        return args.get('app_name') in {'calc', 'mspaint'}
    # No implicit owner location lookup in a shared conversation.
    if name == 'realtime' and args.get('action') == 'get_weather':
        return bool(str(args.get('city') or '').strip())
    return True


def set_permission(payload):
    with identity._profile_lock:
        data = identity._read()
        profiles = data.get('profiles', [])
        if not identity.authorize_management(payload.get('admin_password'), [p for p in profiles if p.get('role') == 'admin']):
            raise ValueError('Senha do administrador inválida.')
        profile = next((p for p in profiles if p.get('id') == payload.get('profile_id')), None)
        if not profile or profile.get('role') == 'admin':
            raise ValueError('Selecione um usuário comum para alterar a permissão.')
        level = payload.get('level')
        if level is None and isinstance(payload.get('allowed'), bool):
            level = 'user' if payload['allowed'] else 'visitor'
        if level not in {'visitor', 'user', 'delegate'}:
            raise ValueError('Selecione visitante, usuário autorizado ou administrador delegado.')
        profile['command_level'] = level
        profile['permissions'] = []  # Legacy grants must not expose the owner's personal data.
        identity._write(data)
        return {'ok': True, 'profile': identity.IdentityService._public(profile)}
