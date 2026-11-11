"""Intenção de vídeo compartilhada pelo registro e pelos adaptadores de tools."""
from __future__ import annotations

import re
from urllib.parse import urlparse
from app.agent.loop_policy import normalize


def youtube_url(text: str) -> str | None:
    for match in re.finditer(r"(?<![\w.@/=-])(?:https?://)?(?:[\w-]+\.)*(?:youtube\.com|youtu\.be)(?=[/:?\s]|$)[^\s]*", text or "", re.I):
        url = match.group().rstrip(".,;)]}")
        host = (urlparse(url if "://" in url else "https://" + url).hostname or "").lower()
        if host in {"youtube.com", "youtu.be"} or host.endswith(".youtube.com"):
            return url
    return None


def is_video_analysis_request(text: str) -> bool:
    value = normalize(text)
    has_video = bool(youtube_url(text) or re.search(r"\bvideo|\bgravacao|\.(?:mp4|mkv|webm)\b", value))
    analysis = bool(re.search(r"\banalis\w*|\bresum\w*|\btranscri\w*|\btimestamps?\b|\btopicos?\b|\bmomentos?\b|\bconteudo\b", value))
    if has_video and analysis:
        return True
    if re.search(r"\b(?:abr[ae]|abrir|toque|toca|tocar|reproduz\w*|play|assisti\w*|open_url)\b", value):
        return False
    return bool(youtube_url(text) or re.search(r"\btranscricao\b|\btimestamps?\b", value))
