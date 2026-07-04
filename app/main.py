from __future__ import annotations

import argparse
import threading
import time

from app.config import load_settings
from app.agent.orchestrator import AgentOrchestrator
from app.services.llm import LLMService
from app.ui.panel import PanelServer


def build_app() -> tuple[AgentOrchestrator, PanelServer]:
    settings = load_settings()
    llm_service = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm_service)
    panel = PanelServer(settings=settings)
    return orchestrator, panel


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis Rebuild: modular desktop assistant")
    parser.add_argument("--demo", action="store_true", help="Executa uma demonstração simples")
    args = parser.parse_args()

    orchestrator, panel = build_app()
    print(f"Iniciando {orchestrator.settings.app_name}...")

    if args.demo:
        print("Abrindo painel de demonstração...")
        panel.start()
        plan = orchestrator.handle_request("Liste meus arquivos na pasta Downloads")
        print("Plano gerado:")
        print(f"  Intenção: {plan.intent}")
        print(f"  Resumo: {plan.summary}")
        print(f"  Ações: {plan.actions}")
        print("Painel disponível em http://127.0.0.1:8000")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("Encerrando...")
    else:
        print("Use --demo para iniciar a demonstração do Jarvis Rebuild.")


if __name__ == "__main__":
    main()
