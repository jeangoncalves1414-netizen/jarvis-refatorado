"""Runtime modes for the agent - defines operation modes and resolution results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentMode(Enum):
    """Operation modes for the agent."""
    CHAT = "chat"
    TUTOR = "tutor"
    WEB = "web"
    VISION = "vision"
    FILES = "files"
    PC = "pc"
    NEXUS = "nexus"
    WORKFLOW = "workflow"
    NEWS = "news"
    PSYCH_COACH = "psych_coach"


@dataclass(frozen=True)
class ModeResolution:
    """Result of mode resolution with confidence score."""
    mode: AgentMode
    confidence: float
    reason: str
    explicit: bool = False
    risky: bool = False
    open_window: bool = False
