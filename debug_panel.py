import os
import sys
sys.path.insert(0, os.getcwd())

from app.config import load_settings
from app.ui.panel.server import PanelServer
from app.agent.orchestrator import AgentOrchestrator
from app.services.llm import LLMService

import urllib.request
import time

settings = load_settings()
llm = LLMService(settings=settings)
orch = AgentOrchestrator(settings=settings, llm_service=llm)
panel = PanelServer(settings=settings)
panel.set_orchestrator(orch)
panel.start()

print('server started')

# Wait for server thread to start
for i in range(5):
    time.sleep(0.5)
    print('waiting', i)

try:
    resp = urllib.request.urlopen('http://127.0.0.1:8000/api/sessions')
    print('status', resp.status)
    print(resp.read().decode('utf-8'))
except Exception as e:
    print('error', type(e).__name__, e)

try:
    resp = urllib.request.urlopen('http://127.0.0.1:8000/')
    print('root status', resp.status)
    content = resp.read(200).decode('utf-8', errors='replace')
    print('root first 200 chars:')
    print(content)
except Exception as e:
    print('root error', type(e).__name__, e)
