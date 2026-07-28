from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AGENTS_FILE = Path("data/agents.json")
TRASH_FILE = Path("data/agents_trash.json")

# Vozes Edge-TTS PT-BR comuns
EDGE_VOICES_PT_BR = [
    "pt-BR-AntonioNeural",   # Masculina
    "pt-BR-FranciscaNeural", # Feminina
    "pt-BR-ThalitaNeural",   # Feminina
    "pt-BR-GiovannaNeural",  # Feminina (jovem)
]


@dataclass
class AgentProfile:
    """Perfil completo de um agente de IA."""
    id: str = ""
    name: str = "Assistente"
    persona: str = "Você é uma assistente virtual amigável e prestativa."
    # TTS
    tts_provider: str = "edge"           # edge, local
    tts_voice: str = "pt-BR-FranciscaNeural"
    tts_speed: float = 1.0               # Multiplicador de velocidade (0.5 a 2.0)
    # Memória
    memory_collection: str = ""          # Nome da coleção ChromaDB (isolada)
    # Metadados
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.memory_collection:
            # Gera nome de coleção seguro (só alfanuméricos e underscore)
            safe_name = "".join(c if c.isalnum() else "_" for c in self.name.lower())
            self.memory_collection = f"agent_{safe_name}_{self.id[:6]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class AgentManager:
    """
    Gerencia o ciclo de vida dos agentes: criar, editar, deletar, restaurar.
    Persiste em JSON local. Thread-safe para acesso básico.
    """

    def __init__(self):
        self._agents: dict[str, AgentProfile] = {}
        self._trash: dict[str, AgentProfile] = {}
        self._active_agent_id: str = ""
        self._load()

    def _load(self):
        """Carrega agentes do disco. Cria um agente padrão se não existir nenhum."""
        AGENTS_FILE.parent.mkdir(parents=True, exist_ok=True)

        if AGENTS_FILE.exists():
            try:
                raw = json.loads(AGENTS_FILE.read_text(encoding="utf-8"))
                for data in raw.get("agents", []):
                    agent = AgentProfile(**{k: v for k, v in data.items() if k in AgentProfile.__dataclass_fields__})
                    self._agents[agent.id] = agent
                self._active_agent_id = raw.get("active_agent_id", "")
            except Exception as e:
                logger.error(f"[AgentManager] Falha ao carregar agents.json: {e}")

        if TRASH_FILE.exists():
            try:
                raw = json.loads(TRASH_FILE.read_text(encoding="utf-8"))
                for data in raw:
                    agent = AgentProfile(**{k: v for k, v in data.items() if k in AgentProfile.__dataclass_fields__})
                    self._trash[agent.id] = agent
            except Exception as e:
                logger.error(f"[AgentManager] Falha ao carregar lixeira: {e}")

        # Se não existir nenhum agente, cria o padrão
        if not self._agents:
            default_agent = AgentProfile(
                name="Jarvis",
                persona="Você é Jarvis, um assistente pessoal inteligente e prestativo. Responda em português brasileiro de forma clara e concisa."
            )
            self._agents[default_agent.id] = default_agent
            self._active_agent_id = default_agent.id
            self._save()

    def _save(self):
        """Persiste agentes no disco."""
        try:
            data = {
                "agents": [
                    {k: v for k, v in agent.__dict__.items() if not k.startswith("_")}
                    for agent in self._agents.values()
                ],
                "active_agent_id": self._active_agent_id
            }
            AGENTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"[AgentManager] Falha ao salvar agents.json: {e}")

    def _save_trash(self):
        """Persiste lixeira no disco."""
        try:
            data = [
                {k: v for k, v in agent.__dict__.items() if not k.startswith("_")}
                for agent in self._trash.values()
            ]
            TRASH_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"[AgentManager] Falha ao salvar lixeira: {e}")

    # ── CRUD ──

    def create_agent(self, name: str, persona: str = "", **kwargs) -> AgentProfile:
        """Cria um novo agente."""
        agent = AgentProfile(
            name=name,
            persona=persona or "Você é uma assistente virtual amigável.",
            **kwargs
        )
        self._agents[agent.id] = agent
        self._save()
        return agent

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        """Retorna um agente por ID."""
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentProfile]:
        """Lista todos os agentes."""
        return list(self._agents.values())

    def update_agent(self, agent_id: str, **kwargs) -> bool:
        """Atualiza um agente existente."""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        
        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        agent.updated_at = datetime.now().isoformat()
        self._save()
        return True

    def delete_agent(self, agent_id: str) -> bool:
        """Move agente para lixeira."""
        agent = self._agents.pop(agent_id, None)
        if not agent:
            return False
        
        self._trash[agent.id] = agent
        self._save_trash()
        
        # Se deletou o agente ativo, ativa outro
        if agent_id == self._active_agent_id:
            self._active_agent_id = next(iter(self._agents.keys()), "")
        
        self._save()
        return True

    def restore_agent(self, agent_id: str) -> bool:
        """Restaura agente da lixeira."""
        agent = self._trash.pop(agent_id, None)
        if not agent:
            return False
        
        self._agents[agent.id] = agent
        self._save_trash()
        self._save()
        return True

    # ── Agente Ativo ──

    def get_active_agent(self) -> AgentProfile:
        """Retorna o agente ativo (ou o primeiro se nenhum estiver ativo)."""
        if self._active_agent_id and self._active_agent_id in self._agents:
            return self._agents[self._active_agent_id]
        
        # Fallback para o primeiro agente
        if self._agents:
            first_id = next(iter(self._agents.keys()))
            self._active_agent_id = first_id
            self._save()
            return self._agents[first_id]
        
        # Último fallback: cria agente padrão
        default = AgentProfile()
        self._agents[default.id] = default
        self._active_agent_id = default.id
        self._save()
        return default

    def set_active_agent(self, agent_id: str) -> bool:
        """Define o agente ativo."""
        if agent_id in self._agents:
            self._active_agent_id = agent_id
            self._save()
            return True
        return False
