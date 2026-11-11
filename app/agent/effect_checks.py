"""Verificação de efeito por regra depois de ações com efeito visível (abrir app, tocar mídia, abrir link).

O ``ActionExecutor`` chama ``check_effect`` quando a ferramenta devolve sucesso. A checagem nunca
transforma sucesso em falha (app lento não é erro): ela diz se o efeito foi confirmado, com a
evidência ("processo spotify.exe, janela "Spotify Premium""), ou se não deu para confirmar.
As sondas (processos, títulos de janela, relógio e sono) são injetáveis para os testes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

# Chave global: os testes antigos desligam (fixture autouse em tests/conftest.py).
enabled = True

POLL_SECONDS = 0.5
APP_TIMEOUT = 6.0
SPOTIFY_OPEN_TIMEOUT = 8.0
SPOTIFY_PLAY_TIMEOUT = 10.0
SPOTIFY_CONTROL_TIMEOUT = 3.0
URL_TIMEOUT = 8.0

BROWSERS = ("chrome", "msedge", "firefox", "brave", "opera")
_SPOTIFY_IDLE_TITLES = frozenset({"spotify", "spotify free", "spotify premium"})
# Executáveis com nome diferente do apelido (Calculadora moderna, Windows Terminal).
_EXTRA_STEMS = {"calc": ("calculatorapp",), "wt": ("windowsterminal",), "explorer": ("explorer",)}


@dataclass(frozen=True)
class EffectCheck:
    status: str  # confirmed | unconfirmed | not_applicable
    evidence: str = ""

    def text(self) -> str:
        if self.status == "confirmed":
            return f"Confirmado: {self.evidence}."
        if self.status == "unconfirmed":
            return f"Não consegui confirmar o efeito: {self.evidence}."
        return ""

    def as_dict(self) -> dict[str, str]:
        return {"status": self.status, "evidence": self.evidence}


NOT_APPLICABLE = EffectCheck("not_applicable")


# ------------------------------------------------------------------ sondas (injetáveis)
def _list_processes() -> set[str]:
    import psutil

    names: set[str] = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").strip().lower()
        except Exception:
            continue
        if name:
            names.add(name)
    return names


def _enum_windows() -> list[tuple[str, int]]:
    """Títulos das janelas visíveis com o PID dono: ``[(título, pid)]``."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[tuple[str, int]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                found.append((buffer.value, int(pid.value)))
        return True

    user32.EnumWindows(callback, 0)
    return found


def _list_window_titles() -> list[str]:
    return [title for title, _pid in _enum_windows()]


def _read_spotify_title() -> str:
    """Título da janela principal do Spotify ("Artista - Música" quando toca; "Spotify Premium" parado)."""
    import psutil

    pids = set()
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if (proc.info.get("name") or "").lower() == "spotify.exe":
                pids.add(int(proc.info["pid"]))
        except Exception:
            continue
    titles = [title.strip() for title, pid in _enum_windows() if pid in pids and title.strip()]
    playing = [title for title in titles if " - " in title and title.casefold() not in _SPOTIFY_IDLE_TITLES]
    return (playing or titles or [""])[0]


_processes: Callable[[], set[str]] = _list_processes
_window_titles: Callable[[], list[str]] = _list_window_titles
_spotify_title: Callable[[], str] = _read_spotify_title
_sleep: Callable[[float], None] = time.sleep
_monotonic: Callable[[], float] = time.monotonic


def _poll(probe: Callable[[], Any], timeout: float) -> Any:
    """Repete ``probe`` a cada 0,5 s até ela devolver algo verdadeiro ou o prazo acabar."""
    deadline = _monotonic() + timeout
    while True:
        found = probe()
        if found:
            return found
        if _monotonic() >= deadline:
            return found
        _sleep(POLL_SECONDS)


# ------------------------------------------------------------------ regras
def _operation(args: dict[str, Any]) -> str:
    return str(args.get("action") or args.get("command") or "").strip().lower()


def _stem(process: str) -> str:
    return process[:-4] if process.endswith(".exe") else process


def _app_stems(name: str) -> set[str]:
    raw = " ".join(str(name or "").split()).lower()
    stems = {_stem(raw.replace("\\", "/").rsplit("/", 1)[-1])}
    try:
        from app.services.app_manager import APP_ALIASES
        alias = APP_ALIASES.get(raw)
        if alias:
            stems.add(alias)
    except Exception:
        pass
    for stem in list(stems):
        stems.update(_EXTRA_STEMS.get(stem, ()))
    return {stem for stem in stems if stem}


def _check_open_app(args: dict[str, Any], result: Any) -> EffectCheck:
    name = str(args.get("app_name") or args.get("command") or "").strip()
    if not name:
        return NOT_APPLICABLE
    if (getattr(result, "data", None) or {}).get("already_running"):
        return EffectCheck("confirmed", f"{name} já estava aberto")
    stems = _app_stems(name)
    words = {word for word in {name.lower(), *stems} if len(word) >= 3}

    def probe() -> str:
        process = next((p for p in sorted(_processes()) if _stem(p) in stems), "")
        title = next((t for t in _window_titles() if any(word in t.lower() for word in words)), "")
        if process and title:
            return f'processo {process}, janela "{title}"'
        if process:
            return f"processo {process} em execução"
        return f'janela "{title}"' if title else ""

    found = _poll(probe, APP_TIMEOUT)
    if found:
        return EffectCheck("confirmed", found)
    return EffectCheck("unconfirmed", f"não encontrei o processo nem a janela de {name} em {int(APP_TIMEOUT)} s")


def _check_spotify(operation: str, before: Any) -> EffectCheck:
    if operation == "open":
        def probe() -> str:
            if "spotify.exe" not in _processes():
                return ""
            title = next((t for t in _window_titles() if "spotify" in t.lower()), "")
            return 'processo Spotify.exe' + (f', janela "{title}"' if title else "")

        found = _poll(probe, SPOTIFY_OPEN_TIMEOUT)
        return EffectCheck("confirmed", found) if found else EffectCheck("unconfirmed", "o processo do Spotify não apareceu")
    if operation == "search_play":
        def playing() -> str:
            title = (_spotify_title() or "").strip()
            return title if isinstance(before, str) and title != before and " - " in title and title.casefold() not in _SPOTIFY_IDLE_TITLES else ""

        title = _poll(playing, SPOTIFY_PLAY_TIMEOUT)
        if title:
            return EffectCheck("confirmed", f'a janela do Spotify passou a mostrar "{title}"; áudio não verificado')
        return EffectCheck("unconfirmed", "não observei uma nova faixa no Spotify após o pedido")
    if operation in {"play_pause", "next", "previous"}:
        previous = before if isinstance(before, str) else None
        if previous is None:
            return EffectCheck("unconfirmed", "não li o estado do Spotify antes do comando")
        def changed() -> str:
            now = (_spotify_title() or "").strip()
            return now if now and now != previous else ""

        title = _poll(changed, SPOTIFY_CONTROL_TIMEOUT)
        if title:
            return EffectCheck("confirmed", f'o Spotify passou de "{previous or "sem título"}" para "{title}"')
        return EffectCheck("unconfirmed", "o título do Spotify não mudou depois do comando")
    return NOT_APPLICABLE


def _url_key(url: str) -> tuple[str, bool]:
    """Palavra que deve aparecer no título da janela e se é página de vídeo/busca do YouTube."""
    parsed = urlparse(url if "://" in url else "https://" + url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        page = host == "youtu.be" or parsed.path.startswith(("/watch", "/results", "/shorts"))
        return "youtube", page
    return host.split(".")[0] if host else "", False


def _check_open_url(args: dict[str, Any], result: Any) -> EffectCheck:
    data = getattr(result, "data", None) or {}
    url = str(data.get("url") or args.get("url") or args.get("query") or "").strip()
    key, youtube_page = _url_key(url)
    if not key:
        return NOT_APPLICABLE
    youtube = key == "youtube"

    def matching() -> tuple[str, str]:
        processes = _processes()
        browser = next((p for p in sorted(processes) if _stem(p) in BROWSERS), "")
        if not browser:
            return "", ""
        titles = [t for t in _window_titles() if key in t.lower()]
        if youtube_page:
            # "Lofi - YouTube - Google Chrome": a parte antes de "YouTube" é o vídeo ou a busca.
            loaded = [t for t in titles if t.lower().split("youtube", 1)[0].strip(" -–") != ""]
            if loaded:
                return browser, loaded[0]
            return browser, ""
        return browser, (titles[0] if titles else "")

    state = {"browser": "", "plain": ""}

    def probe() -> str:
        browser, title = matching()
        state["browser"] = browser or state["browser"]
        if youtube_page and not title and browser:
            state["plain"] = next((t for t in _window_titles() if "youtube" in t.lower()), state["plain"])
        return f'{browser}|{title}' if browser and title else ""

    found = _poll(probe, URL_TIMEOUT)
    if found:
        browser, title = found.split("|", 1)
        if youtube_page:
            return EffectCheck("confirmed", f'abri o vídeo no YouTube (navegador {browser}, janela "{title}"); não consigo confirmar que está tocando')
        label = "o YouTube" if youtube else key
        return EffectCheck("confirmed", f'abri {label} (navegador {browser}, janela "{title}")')
    if not state["browser"]:
        return EffectCheck("unconfirmed", "nenhum navegador apareceu aberto")
    if youtube_page and state["plain"]:
        return EffectCheck("unconfirmed", "abri o YouTube, mas o vídeo não apareceu no título da janela")
    return EffectCheck("unconfirmed", f'o navegador abriu, mas nenhuma janela mostra "{key}"')


def capture_before(tool: str, args: dict[str, Any]) -> Any:
    """Estado lido antes da ação (só controles do Spotify, barato)."""
    if not enabled or tool != "spotify" or _operation(args or {}) not in {"play_pause", "next", "previous", "search_play"}:
        return None
    try:
        return (_spotify_title() or "").strip()
    except Exception:
        return None


def check_effect(tool: str, args: dict[str, Any] | None, result: Any, before: Any = None) -> EffectCheck:
    """Confirma o efeito visível da ação; ferramentas sem efeito observável devolvem ``not_applicable``."""
    if not enabled:
        return NOT_APPLICABLE
    args = args or {}
    operation = _operation(args)
    if tool == "open_windows_app":
        operation = str(args.get("action") or "open").strip().lower()
    if (tool == "open_windows_app" and operation == "open") or (tool in {"system_control", "desktop_automation"} and operation == "open_app"):
        return _check_open_app(args, result)
    if tool == "spotify":
        return _check_spotify(operation, before)
    if (tool == "web_search" and operation == "open_url") or (tool == "desktop_automation" and operation == "open_url"):
        return _check_open_url(args, result)
    data = getattr(result, "data", None) or {}
    if tool == "file_manager" and operation in {"mkdir", "create_dir"}:
        from pathlib import Path
        path = data.get("path")
        if path and Path(path).is_dir():
            return EffectCheck("confirmed", f"pasta existente em {path}")
        return EffectCheck("unconfirmed", "a pasta criada não foi encontrada no caminho retornado")
    if tool == "timer" and operation in {"set_timer", "set_alarm"}:
        from app.agent.tools.timer import list_active_timers
        if any(t["label"] == data.get("label") and t["fire_at"] == data.get("fire_at") for t in list_active_timers()):
            return EffectCheck("confirmed", f"alarme registrado para {data['fire_at']}; o disparo sonoro ainda não ocorreu")
        return EffectCheck("unconfirmed", "não encontrei o alarme no registro de timers ativos")
    if tool == "script_runner":
        if data.get("exit_code") == 0 and not data.get("needs_confirmation"):
            return EffectCheck("confirmed", "processo do script terminou com código 0; efeitos externos não foram verificados")
        return EffectCheck("unconfirmed", "não há código de saída do processo")
    if tool == "media_tool" and operation in {"play_motivational", "reveal_in_folder"}:
        return EffectCheck("unconfirmed", "pedido enviado ao player ou Explorer; sem confirmação da interface")
    return NOT_APPLICABLE
