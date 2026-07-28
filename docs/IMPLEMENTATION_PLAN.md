# Plano de Implementação Jarvis Rebuild
## Versão 1.0 - Estruturado para Manutenibilidade

## Princípios de Arquitetura

### 1. **Modularidade Extrema**
- Cada módulo ≤ 300 linhas
- Responsabilidade única por arquivo
- Interfaces claras entre módulos
- Zero acoplamento desnecessário

### 2. **Padrões de Código**
- Type hints obrigatórios
- Docstrings mínimas (1 linha)
- Nomes descritivos mas curtos
- Zero comentários redundantes

### 3. **Estrutura de Diretórios**
```
app/
├── core/              # Core systems (rate limit, guardrails, etc)
├── agent/             # Agent logic (orchestrator, models)
├── tools/             # Individual tools (≤ 200 linhas cada)
├── services/          # External integrations (vision, browser, etc)
├── storage/           # Data persistence
├── plugins/           # Plugin system
└── utils/             # Pure utilities (no business logic)
```

### 4. **Limites de Tamanho**
- Arquivos: 200-300 linhas máximo
- Funções: ≤ 50 linhas
- Classes: ≤ 150 linhas
- Módulos: ≤ 5 classes/funções públicas

### 5. **Padrão de Importação**
```python
# 1. Stdlib
from __future__ import annotations
import os
from pathlib import Path

# 2. Third-party
import chromadb

# 3. Local (absolute imports only)
from app.core.rate_limit import RateLimiter
from app.agent.orchestrator import Orchestrator
```

---

## FASE 1 - Fundamentos de Segurança (CRÍTICO)

### 1.1 Rate Limiting
**Objetivo:** Controlar chamadas API para evitar bloqueios

**Arquivo:** `app/core/rate_limit.py` (≤ 100 linhas)

```python
from __future__ import annotations
import threading
import time
from collections import deque

class RateLimiter:
    """Rate limiter com janela deslizante."""
    def __init__(self, max_per_minute: int = 10):
        self.max = max_per_minute
        self.window = 60.0
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()
    
    def wait(self) -> None:
        """Aguarda slot disponível."""
        while True:
            wait = 0.0
            with self._lock:
                self._clean()
                if len(self._timestamps) < self.max:
                    self._timestamps.append(time.time())
                    return
                wait = self.window - (time.time() - self._timestamps[0])
            time.sleep(max(0.1, wait))
    
    def _clean(self) -> None:
        """Remove timestamps antigos."""
        cutoff = time.time() - self.window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
```

**Dependências:** Nenhuma
**Testes:** Testar limite de 10 requisições/minuto

---

### 1.2 Tool Guardrails
**Objetivo:** Prevenir loops e chamadas repetidas

**Arquivo:** `app/core/guardrails.py` (≤ 120 linhas)

```python
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass
class GuardrailDecision:
    allow: bool
    reason: str = ""

class ToolGuardrails:
    """Proteção contra loops e repetições."""
    def __init__(self, repeat_limit: int = 3, no_progress_limit: int = 3):
        self.repeat_limit = repeat_limit
        self.no_progress_limit = no_progress_limit
        self._calls: dict[str, int] = {}
        self._results: dict[tuple[str, str], int] = {}
    
    def before_call(self, tool: str, args: Mapping[str, Any]) -> GuardrailDecision:
        """Verifica antes de executar ferramenta."""
        key = self._key(tool, args)
        if self._calls.get(key, 0) >= self.repeat_limit:
            return GuardrailDecision(False, f"Repetição bloqueada: {tool}")
        self._calls[key] = self._calls.get(key, 0) + 1
        return GuardrailDecision(True)
    
    def after_call(self, tool: str, args: Mapping[str, Any], result: Any) -> GuardrailDecision:
        """Verifica após executar ferramenta."""
        text = self._normalize(result)
        key = (tool, text)
        self._results[key] = self._results.get(key, 0) + 1
        
        if self._results[key] >= self.no_progress_limit and self._is_no_progress(text):
            return GuardrailDecision(False, f"Sem progresso: {tool}")
        return GuardrailDecision(True)
    
    def reset(self) -> None:
        """Reseta contadores."""
        self._calls.clear()
        self._results.clear()
    
    def _key(self, tool: str, args: Mapping[str, Any]) -> str:
        try:
            return f"{tool}:{json.dumps(args or {}, sort_keys=True)}"
        except TypeError:
            return f"{tool}:{repr(args)}"
    
    def _normalize(self, result: Any) -> str:
        return " ".join(str(result or "").lower().split())[:200]
    
    def _is_no_progress(self, text: str) -> bool:
        markers = {"sem resultado", "falhou", "erro", "não executado"}
        return any(m in text for m in markers)
```

**Dependências:** Nenhuma
**Testes:** Testar bloqueio de repetições e detecção de no-progress

---

### 1.3 Critical Confirmation
**Objetivo:** Confirmar ações sensíveis

**Arquivo:** `app/core/critical_confirm.py` (≤ 150 linhas)

```python
from __future__ import annotations
import json
import threading
import uuid
from pathlib import Path

CONFIRM_FILE = Path("data/critical_confirm.json")

class CriticalConfirm:
    """Sistema de confirmação para ações críticas."""
    def __init__(self, enabled: bool = True):
        self.enabled = self._load_pref(enabled)
        self._lock = threading.Lock()
        self._pending: dict | None = None
        self._done = threading.Event()
        self._approved = False
    
    def _load_pref(self, default: bool) -> bool:
        if not CONFIRM_FILE.exists():
            return default
        try:
            data = json.loads(CONFIRM_FILE.read_text())
            return data.get("enabled", default)
        except Exception:
            return default
    
    def save_pref(self, enabled: bool) -> None:
        CONFIRM_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIRM_FILE.write_text(json.dumps({"enabled": enabled}))
        self.enabled = enabled
    
    def request(self, tool: str, detail: str = "") -> bool:
        """Solicita confirmação para ação crítica."""
        if not self.enabled:
            return True
        
        req_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._pending = {"id": req_id, "tool": tool, "detail": detail}
            self._approved = False
            self._done.clear()
        
        print(f"\n[CONFIRMAÇÃO] {detail or f'Executar {tool}?'}")
        print("Confirme no painel ou diga 'confirmar'/'cancelar'")
        
        # Timeout de 5 minutos
        if self._done.wait(timeout=300):
            with self._lock:
                return self._approved
        return False
    
    def resolve(self, req_id: str, approved: bool) -> bool:
        """Resolve confirmação pendente."""
        with self._lock:
            if not self._pending or self._pending["id"] != req_id:
                return False
            self._approved = approved
            self._pending = None
        self._done.set()
        return True
    
    def get_pending(self) -> dict | None:
        """Retorna requisição pendente."""
        with self._lock:
            return dict(self._pending) if self._pending else None
```

**Dependências:** Nenhuma
**Testes:** Testar fluxo de confirmação e timeout

---

### 1.4 Telemetria
**Objetivo:** Logging estruturado para analytics

**Arquivo:** `app/core/telemetry.py` (≤ 80 linhas)

```python
from __future__ import annotations
import json
import time
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("data/telemetry.log")

class Telemetry:
    """Logging estruturado simples."""
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, event: str, data: dict) -> None:
        """Registra evento."""
        if not self.enabled:
            return
        entry = {
            "ts": datetime.now().isoformat(),
            "event": event,
            "data": data
        }
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
    
    def log_tool(self, tool: str, ok: bool, ms: int) -> None:
        """Registra execução de ferramenta."""
        self.log("tool_run", {"tool": tool, "ok": ok, "ms": ms})
```

**Dependências:** Nenhuma
**Testes:** Verificar escrita no log

---

## FASE 2 - Automação Windows

### 2.1 App Manager
**Objetivo:** Gerenciar apps via Windows Registry

**Arquivo:** `app/services/app_manager.py` (≤ 200 linhas)

```python
from __future__ import annotations
import ctypes
import subprocess
import winreg
from pathlib import Path
from typing import List

ALIASES = {
    "chrome": "chrome", "navegador": "chrome",
    "notepad": "notepad", "bloco": "notepad",
    "spotify": "spotify", "code": "code",
}

class AppManager:
    """Gerenciamento de aplicativos Windows."""
    def __init__(self):
        self._apps_cache = self._scan_registry()
    
    def _scan_registry(self) -> dict[str, str]:
        """Escaneia registry por apps instalados."""
        apps = {}
        paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        for hive, key_path in paths:
            try:
                key = winreg.OpenKey(hive, key_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey = winreg.OpenKey(key, winreg.EnumKey(key, i))
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        if name:
                            apps[name.lower()] = name
                        winreg.CloseKey(subkey)
                    except Exception:
                        continue
                winreg.CloseKey(key)
            except Exception:
                continue
        return apps
    
    def find_app(self, query: str) -> str | None:
        """Busca app por nome."""
        query = query.lower()
        if query in ALIASES:
            return ALIASES[query]
        
        for name_lower, name in self._apps_cache.items():
            if query in name_lower:
                return name
        return None
    
    def open_app(self, name: str) -> bool:
        """Abre aplicativo."""
        resolved = self.find_app(name)
        if not resolved:
            return False
        
        try:
            subprocess.Popen([resolved], shell=True)
            return True
        except Exception:
            return False
    
    def open_batch(self, names: List[str]) -> dict[str, bool]:
        """Abre múltiplos apps."""
        return {name: self.open_app(name) for name in names}
```

**Dependências:** Nenhuma (Windows-only)
**Testes:** Testar busca e abertura de apps

---

### 2.2 Window Control
**Objetivo:** Controlar janelas (foco, minimizar, fechar)

**Arquivo:** `app/services/window_control.py` (≤ 120 linhas)

```python
from __future__ import annotations
import ctypes
import time

class WindowControl:
    """Controle básico de janelas Windows."""
    def __init__(self):
        self.user32 = ctypes.windll.user32
    
    def find_window(self, title: str) -> int | None:
        """Encontra janela por título."""
        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        def callback(hwnd, _):
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                self.user32.GetWindowTextW(hwnd, buff, length + 1)
                if title.lower() in buff.value.lower():
                    callback.hwnd = hwnd
                    return False
            return True
        
        callback.hwnd = None
        self.user32.EnumWindows(callback, 0)
        return callback.hwnd
    
    def focus_window(self, hwnd: int) -> bool:
        """Foca janela."""
        try:
            if self.user32.IsIconic(hwnd):
                self.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            self.user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False
    
    def close_window(self, hwnd: int) -> bool:
        """Fecha janela."""
        try:
            self.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            return True
        except Exception:
            return False
```

**Dependências:** Nenhuma (Windows-only)
**Testes:** Testar foco e fechamento de janelas

---

## FASE 3 - Visão e Web

### 3.1 Vision Service
**Objetivo:** Captura e análise de tela

**Arquivo:** `app/services/vision.py` (≤ 180 linhas)

```python
from __future__ import annotations
import base64
from io import BytesIO
from mss import mss
from PIL import Image
from google import genai
from google.genai import types

class VisionService:
    """Serviço de visão com Gemini."""
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model
    
    def capture_screen(self) -> bytes:
        """Captura tela como bytes."""
        with mss() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            return screenshot.rgb
    
    def capture_pil(self) -> Image.Image:
        """Captura tela como PIL Image."""
        raw = self.capture_screen()
        return Image.frombytes("RGB", raw.size, raw.rgb)
    
    def analyze(self, prompt: str) -> str:
        """Analisa tela com prompt."""
        image = self.capture_pil()
        
        # Reduz tamanho se muito grande
        if image.width > 1280 or image.height > 720:
            image.thumbnail((1280, 720))
        
        # Converte para base64
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(
                    data=base64.b64decode(image_b64),
                    mime_type="image/jpeg"
                ),
                prompt
            ]
        )
        return response.text
```

**Dependências:** mss, Pillow, google-genai
**Testes:** Testar captura e análise

---

### 3.2 Browser Agent
**Objetivo:** Navegação web automatizada

**Arquivo:** `app/services/browser_agent.py` (≤ 150 linhas)

```python
from __future__ import annotations
from playwright.sync_api import sync_playwright

class BrowserAgent:
    """Automação web com Playwright."""
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None
    
    def start(self) -> None:
        """Inicia navegador."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page()
    
    def stop(self) -> None:
        """Para navegador."""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
    
    def goto(self, url: str) -> None:
        """Navega para URL."""
        self._page.goto(url)
    
    def click(self, selector: str) -> None:
        """Clica em elemento."""
        self._page.click(selector)
    
    def fill(self, selector: str, text: str) -> None:
        """Preenche campo."""
        self._page.fill(selector, text)
    
    def text(self, selector: str) -> str:
        """Retorna texto de elemento."""
        return self._page.text_content(selector) or ""
    
    def screenshot(self) -> bytes:
        """Captura screenshot."""
        return self._page.screenshot()
```

**Dependências:** playwright
**Testes:** Testar navegação básica

---

## FASE 4 - Sistema e Utilitários

### 4.1 Cron Scheduler
**Objetivo:** Agendamento de tarefas

**Arquivo:** `app/core/scheduler.py` (≤ 100 linhas)

```python
from __future__ import annotations
import threading
import time
from typing import Callable

class Scheduler:
    """Scheduler simples baseado em intervalos."""
    def __init__(self):
        self._jobs: list[dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
    
    def add_job(self, func: Callable, interval: float) -> None:
        """Adiciona job recorrente."""
        with self._lock:
            self._jobs.append({"func": func, "interval": interval, "last": 0})
    
    def start(self) -> None:
        """Inicia scheduler."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Para scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _loop(self) -> None:
        """Loop principal."""
        while self._running:
            now = time.time()
            with self._lock:
                for job in self._jobs:
                    if now - job["last"] >= job["interval"]:
                        try:
                            job["func"]()
                        except Exception:
                            pass
                        job["last"] = now
            time.sleep(1)
```

**Dependências:** Nenhuma
**Testes:** Testar execução de jobs

---

### 4.2 Heartbeat
**Objetivo:** Monitoramento de saúde

**Arquivo:** `app/core/heartbeat.py` (≤ 80 linhas)

```python
from __future__ import annotations
import time
from threading import Thread

class Heartbeat:
    """Monitor de saúde do sistema."""
    def __init__(self, interval: float = 30.0):
        self.interval = interval
        self._last_beat = time.time()
        self._running = False
        self._thread = None
    
    def start(self) -> None:
        """Inicia heartbeat."""
        if self._running:
            return
        self._running = True
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """Para heartbeat."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _loop(self) -> None:
        """Loop de heartbeat."""
        while self._running:
            self._last_beat = time.time()
            time.sleep(self.interval)
    
    def is_alive(self) -> bool:
        """Verifica se sistema está vivo."""
        return (time.time() - self._last_beat) < (self.interval * 2)
```

**Dependências:** Nenhuma
**Testes:** Verificar heartbeat

---

### 4.3 Clap Detector
**Objetivo:** Detecção de palmas

**Arquivo:** `app/services/clap_detector.py` (≤ 100 linhas)

```python
from __future__ import annotations
import numpy as np
from typing import Callable

class ClapDetector:
    """Detecção de palmas via áudio."""
    def __init__(self, threshold: float = 0.8, callback: Callable | None = None):
        self.threshold = threshold
        self.callback = callback
        self._listening = False
    
    def process_audio(self, audio_data: np.ndarray) -> bool:
        """Processa frame de áudio."""
        if not self._listening:
            return False
        
        # Calcula energia do sinal
        energy = np.mean(np.abs(audio_data))
        
        if energy > self.threshold:
            if self.callback:
                self.callback()
            return True
        return False
    
    def start(self) -> None:
        """Inicia detecção."""
        self._listening = True
    
    def stop(self) -> None:
        """Para detecção."""
        self._listening = False
```

**Dependências:** numpy
**Testes:** Testar detecção com áudio

---

### 4.4 File Processor
**Objetivo:** Processamento avançado de arquivos

**Arquivo:** `app/services/file_processor.py` (≤ 120 linhas)

```python
from __future__ import annotations
import shutil
from pathlib import Path
from typing import List

class FileProcessor:
    """Operações avançadas de arquivos."""
    @staticmethod
    def batch_move(src_patterns: List[str], dst: Path) -> dict[str, bool]:
        """Move arquivos por padrão."""
        results = {}
        for pattern in src_patterns:
            for src in Path(".").glob(pattern):
                try:
                    shutil.move(str(src), str(dst))
                    results[str(src)] = True
                except Exception:
                    results[str(src)] = False
        return results
    
    @staticmethod
    def batch_copy(src_patterns: List[str], dst: Path) -> dict[str, bool]:
        """Copia arquivos por padrão."""
        results = {}
        for pattern in src_patterns:
            for src in Path(".").glob(pattern):
                try:
                    shutil.copy2(str(src), str(dst))
                    results[str(src)] = True
                except Exception:
                    results[str(src)] = False
        return results
    
    @staticmethod
    def get_metadata(path: Path) -> dict:
        """Retorna metadados de arquivo."""
        stat = path.stat()
        return {
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
            "extension": path.suffix
        }
```

**Dependências:** Nenhuma
**Testes:** Testar operações batch

---

### 4.5 Settings Manager
**Objetivo:** Gerenciamento de configurações

**Arquivo:** `app/core/settings_manager.py` (≤ 100 linhas)

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

SETTINGS_FILE = Path("data/settings.json")

class SettingsManager:
    """Gerenciador de configurações."""
    def __init__(self):
        self._settings = self._load()
    
    def _load(self) -> dict:
        if not SETTINGS_FILE.exists():
            return {}
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            return {}
    
    def save(self) -> None:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(self._settings, indent=2))
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self.save()
    
    def delete(self, key: str) -> None:
        self._settings.pop(key, None)
        self.save()
```

**Dependências:** Nenhuma
**Testes:** Testar CRUD de settings

---

### 4.6 User Manager
**Objetivo:** Gerenciamento multi-usuário

**Arquivo:** `app/core/user_manager.py` (≤ 120 linhas)

```python
from __future__ import annotations
import json
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import List

USERS_FILE = Path("data/users.json")

@dataclass
class User:
    id: str
    name: str
    permissions: List[str]

class UserManager:
    """Gerenciamento de usuários."""
    def __init__(self):
        self._users = self._load()
    
    def _load(self) -> dict[str, User]:
        if not USERS_FILE.exists():
            return {}
        try:
            data = json.loads(USERS_FILE.read_text())
            return {u["id"]: User(**u) for u in data.get("users", [])}
        except Exception:
            return {}
    
    def save(self) -> None:
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "users": [
                {"id": u.id, "name": u.name, "permissions": u.permissions}
                for u in self._users.values()
            ]
        }
        USERS_FILE.write_text(json.dumps(data, indent=2))
    
    def create(self, name: str, permissions: List[str]) -> User:
        user = User(id=uuid.uuid4().hex[:12], name=name, permissions=permissions)
        self._users[user.id] = user
        self.save()
        return user
    
    def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)
    
    def list(self) -> List[User]:
        return list(self._users.values())
```

**Dependências:** Nenhuma
**Testes:** Testar CRUD de usuários

---

## FASE 5 - Ferramentas Avançadas

### 5.1 Code Helper
**Objetivo:** Assistência de código

**Arquivo:** `app/tools/code_helper.py` (≤ 150 linhas)

```python
from __future__ import annotations
from typing import Any
from .base import BaseTool, ToolResult

class CodeHelperTool(BaseTool):
    @property
    def name(self) -> str:
        return "code_helper"
    
    @property
    def description(self) -> str:
        return "Auxilia em tarefas de código: gerar snippets, explicar, refatorar."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["generate", "explain", "refactor"]},
                "code": {"type": "string"},
                "language": {"type": "string"}
            },
            "required": ["action", "code"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action")
        code = args.get("code", "")
        
        if action == "explain":
            return ToolResult(ok=True, message=f"Explicação: {code[:100]}...")
        elif action == "generate":
            return ToolResult(ok=True, message=f"Snippet gerado para {args.get('language', 'python')}")
        elif action == "refactor":
            return ToolResult(ok=True, message="Código refatorado")
        
        return ToolResult(ok=False, message="Ação desconhecida")
```

**Dependências:** BaseTool
**Testes:** Testar cada ação

---

### 5.2 Image Generator
**Objetivo:** Geração de imagens

**Arquivo:** `app/tools/image_generator.py` (≤ 100 linhas)

```python
from __future__ import annotations
from typing import Any
from .base import BaseTool, ToolResult

class ImageGeneratorTool(BaseTool):
    @property
    def name(self) -> str:
        return "image_generator"
    
    @property
    def description(self) -> str:
        return "Gera imagens via API (placeholder)."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "size": {"type": "string", "enum": ["256x256", "512x512", "1024x1024"]}
            },
            "required": ["prompt"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        prompt = args.get("prompt", "")
        # Placeholder - integrar com API real (DALL-E, Stable Diffusion)
        return ToolResult(ok=True, message=f"Imagem gerada para: {prompt[:50]}...")
```

**Dependências:** BaseTool
**Testes:** Testar geração

---

### 5.3 Hacker Mode
**Objetivo:** Automação avançada

**Arquivo:** `app/tools/hacker_mode.py` (≤ 120 linhas)

```python
from __future__ import annotations
from typing import Any
from .base import BaseTool, ToolResult

class HackerModeTool(BaseTool):
    @property
    def name(self) -> str:
        return "hacker_mode"
    
    @property
    def description(self) -> str:
        return "Executa scripts complexos de automação."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "script": {"type": "string"},
                "args": {"type": "object"}
            },
            "required": ["script"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        script = args.get("script", "")
        # Placeholder - executar script Python seguro
        return ToolResult(ok=True, message=f"Script executado: {script[:50]}...")
```

**Dependências:** BaseTool
**Testes:** Testar execução

---

### 5.4 Workflow
**Objetivo:** Cadeias de tarefas

**Arquivo:** `app/tools/workflow.py` (≤ 150 linhas)

```python
from __future__ import annotations
import json
from typing import Any
from .base import BaseTool, ToolResult

class WorkflowTool(BaseTool):
    @property
    def name(self) -> str:
        return "workflow"
    
    @property
    def description(self) -> str:
        return "Executa cadeias de ferramentas em sequência."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "steps": {"type": "array", "items": {"type": "object"}}
            },
            "required": ["steps"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        steps = args.get("steps", [])
        results = []
        
        for step in steps:
            # Placeholder - executar cada step
            results.append(f"Step executado: {step.get('tool', 'unknown')}")
        
        return ToolResult(ok=True, message=f"Workflow completado: {len(steps)} steps")
```

**Dependências:** BaseTool
**Testes:** Testar workflow

---

### 5.5 MCP Tool
**Objetivo:** Integração Model Context Protocol

**Arquivo:** `app/tools/mcp_tool.py` (≤ 100 linhas)

```python
from __future__ import annotations
from typing import Any
from .base import BaseTool, ToolResult

class MCPTool(BaseTool):
    @property
    def name(self) -> str:
        return "mcp"
    
    @property
    def description(self) -> str:
        return "Integração com serviços via Model Context Protocol."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "server": {"type": "string"},
                "action": {"type": "string"},
                "params": {"type": "object"}
            },
            "required": ["server", "action"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        # Placeholder - integrar com MCP client
        return ToolResult(ok=True, message=f"MCP action: {args.get('action')}")
```

**Dependências:** BaseTool
**Testes:** Testar integração

---

### 5.6 Dev Agent
**Objetivo:** Agente especializado em desenvolvimento

**Arquivo:** `app/tools/dev_agent.py` (≤ 120 linhas)

```python
from __future__ import annotations
from typing import Any
from .base import BaseTool, ToolResult

class DevAgentTool(BaseTool):
    @property
    def name(self) -> str:
        return "dev_agent"
    
    @property
    def description(self) -> str:
        return "Agente especializado em desenvolvimento de software."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {"type": "string", "enum": ["review", "debug", "test"]},
                "code": {"type": "string"}
            },
            "required": ["task"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        task = args.get("task")
        if task == "review":
            return ToolResult(ok=True, message="Code review concluído")
        elif task == "debug":
            return ToolResult(ok=True, message="Debugging realizado")
        elif task == "test":
            return ToolResult(ok=True, message="Testes gerados")
        
        return ToolResult(ok=False, message="Tarefa desconhecida")
```

**Dependências:** BaseTool
**Testes:** Testar cada tarefa

---

### 5.7 Proactive Agent
**Objetivo:** Ações proativas

**Arquivo:** `app/tools/proactive_agent.py` (≤ 100 linhas)

```python
from __future__ import annotations
from typing import Any
from .base import BaseTool, ToolResult

class ProactiveAgentTool(BaseTool):
    @property
    def name(self) -> str:
        return "proactive_agent"
    
    @property
    def description(self) -> str:
        return "Sugere ações proativas baseadas em contexto."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "context": {"type": "string"}
            },
            "required": ["context"]
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        ctx = args.get("context", "")
        # Placeholder - analisar contexto e sugerir ações
        return ToolResult(ok=True, message=f"Sugestão proativa para: {ctx[:50]}...")
```

**Dependências:** BaseTool
**Testes:** Testar sugestões

---

## FASE 6 - Integração Final

### 6.1 Atualizar ToolRegistry
**Arquivo:** `app/agent/tools/registry.py`

Adicionar ao `__init__`:
```python
from app.tools.code_helper import CodeHelperTool
from app.tools.image_generator import ImageGeneratorTool
from app.tools.hacker_mode import HackerModeTool
from app.tools.workflow import WorkflowTool
from app.tools.mcp_tool import MCPTool
from app.tools.dev_agent import DevAgentTool
from app.tools.proactive_agent import ProactiveAgentTool

# No _register_builtin_tools:
self._register(CodeHelperTool())
self._register(ImageGeneratorTool())
self._register(HackerModeTool())
self._register(WorkflowTool())
self._register(MCPTool())
self._register(DevAgentTool())
self._register(ProactiveAgentTool())
```

---

### 6.2 Atualizar Orchestrator
**Arquivo:** `app/agent/orchestrator.py`

Adicionar ao `__init__`:
```python
from app.core.rate_limit import RateLimiter
from app.core.guardrails import ToolGuardrails
from app.core.critical_confirm import CriticalConfirm
from app.core.telemetry import Telemetry

self.rate_limiter = RateLimiter(max_per_minute=10)
self.guardrails = ToolGuardrails()
self.critical_confirm = CriticalConfirm()
self.telemetry = Telemetry()
```

Adicionar ao `execute_tool`:
```python
# Antes de executar
decision = self.guardrails.before_call(name, args)
if not decision.allow:
    return ToolResult(ok=False, message=decision.reason)

# Se for crítico
if getattr(tool, "critical", False):
    if not self.critical_confirm.request(name, str(args)):
        return ToolResult(ok=False, message="Ação cancelada pelo usuário")

# Após executar
decision = self.guardrails.after_call(name, args, result)
if not decision.allow:
    return ToolResult(ok=False, message=decision.reason)

# Log
self.telemetry.log_tool(name, result.ok, 0)
```

---

### 6.3 Atualizar main.py
**Arquivo:** `app/main.py`

Adicionar inicialização:
```python
from app.services.app_manager import AppManager
from app.services.window_control import WindowControl
from app.services.vision import VisionService
from app.services.browser_agent import BrowserAgent
from app.core.scheduler import Scheduler
from app.core.heartbeat import Heartbeat

# Inicializar serviços
app_manager = AppManager()
window_control = WindowControl()
vision_service = VisionService(api_key=settings.gemini_api_key)
browser_agent = BrowserAgent(headless=False)
scheduler = Scheduler()
heartbeat = Heartbeat()

# Passar para orchestrator se necessário
orchestrator.app_manager = app_manager
orchestrator.window_control = window_control
orchestrator.vision_service = vision_service
```

---

## Ordem de Implementação

### Semana 1: Fundamentos (CRÍTICO)
1. Rate Limiting
2. Tool Guardrails
3. Critical Confirmation
4. Telemetria

### Semana 2: Automação Windows
5. App Manager
6. Window Control
7. File Processor

### Semana 3: Visão e Web
8. Vision Service
9. Browser Agent

### Semana 4: Sistema
10. Cron Scheduler
11. Heartbeat
12. Settings Manager
13. User Manager

### Semana 5: Utilitários
14. Clap Detector
15. Audio Events (se necessário)

### Semana 6: Ferramentas Avançadas
16. Code Helper
17. Image Generator
18. Hacker Mode
19. Workflow
20. MCP Tool
21. Dev Agent
22. Proactive Agent

### Semana 7: Integração
23. Atualizar ToolRegistry
24. Atualizar Orchestrator
25. Atualizar main.py
26. Testes finais

---

## Checklist de Validação

### Para Cada Módulo:
- [ ] Arquivo ≤ 300 linhas
- [ ] Funções ≤ 50 linhas
- [ ] Type hints completos
- [ ] Docstring mínima
- [ ] Zero imports desnecessários
- [ ] Tratamento de exceções específico
- [ ] Logging estruturado
- [ ] Testes básicos

### Para Cada Integração:
- [ ] Sem breaking changes
- [ ] Backward compatible
- [ ] Configuração via .env
- [ ] Graceful degradation
- [ ] Documentação atualizada

---

## Padrões a Seguir

### 1. Error Handling
```python
# RUIM
try:
    do_something()
except Exception:
    pass

# BOM
try:
    do_something()
except (ValueError, KeyError) as e:
    logger.error(f"Erro específico: {e}")
    return None
```

### 2. Type Hints
```python
# RUIM
def process(data):
    return data.upper()

# BOM
def process(data: str) -> str:
    return data.upper()
```

### 3. Docstrings
```python
# RUIM
def add(a, b):
    return a + b

# BOM
def add(a: int, b: int) -> int:
    """Soma dois inteiros."""
    return a + b
```

### 4. Imports
```python
# RUIM
from app.core import *
from app.services import *

# BOM
from app.core.rate_limit import RateLimiter
from app.services.vision import VisionService
```

---

## Métricas de Sucesso

### Código:
- Arquivos médios: 150-200 linhas
- Cobertura de tipos: >90%
- Zero warnings de mypy

### Performance:
- Startup < 3 segundos
- Resposta < 500ms (sem LLM)
- Memória < 500MB

### Manutenibilidade:
- Tempo de onboarding < 1 hora
- Bug fixes < 30 minutos
- Novos features < 2 horas

---

## Notas Finais

### Evitar:
- Classes gigantes (>150 linhas)
- Funções monolíticas (>50 linhas)
- Imports globais
- Comentários redundantes
- Abstrações prematuras
- Copy-paste de código

### Priorizar:
- Simplicidade sobre complexidade
- Legibilidade sobre otimização
- Modularidade sobre monolitos
- Padrões sobre convenções
- Testes sobre debugging
- Documentação sobre suposições

Este plano garante código enxuto, manutenível e fácil de estender, evitando os problemas do PROJETO AI.
