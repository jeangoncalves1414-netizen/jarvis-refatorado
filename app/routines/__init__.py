"""Rotinas: sequências de ações gravadas, com gatilhos de horário, voz e comando.

Cada execução vira um Run de origem ``routine`` na Central e cada etapa passa pelo Action Kernel.
"""
from app.routines.templates import (
    ROUTINE_TEMPLATES,
    list_routine_templates,
    get_routine_template,
    install_routine_template,
)
