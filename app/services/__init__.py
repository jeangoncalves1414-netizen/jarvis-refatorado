from __future__ import annotations

from .app_manager import AppManager
from .window_control import WindowControl
from .file_processor import FileProcessor
from .vision import VisionService
from .browser_agent import BrowserAgent
from .calendar import CalendarService, CalendarEvent

try:
    from .clap_detector import ClapDetector
    CLAP_DETECTOR_AVAILABLE = True
except ImportError:
    CLAP_DETECTOR_AVAILABLE = False

try:
    from .notifications import WindowsNotification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

try:
    from .ollama_llm import OllamaLLM
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

__all__ = ["AppManager", "WindowControl", "FileProcessor", "VisionService", "BrowserAgent", "CalendarService", "CalendarEvent"]

if CLAP_DETECTOR_AVAILABLE:
    __all__.append("ClapDetector")

if NOTIFICATIONS_AVAILABLE:
    __all__.append("WindowsNotification")

if OLLAMA_AVAILABLE:
    __all__.append("OllamaLLM")
