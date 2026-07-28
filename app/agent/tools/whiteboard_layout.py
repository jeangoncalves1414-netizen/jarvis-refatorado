from __future__ import annotations

from typing import Any


def estimate_text_height(text: str, size: int = 16, max_width: int = 480) -> int:
    avg_char_width = size * 0.55
    chars_per_line = max(1, int(max_width / avg_char_width))
    lines = (text or "").split("\n")
    total_lines = 0
    for line in lines:
        length = len(line) or 1
        total_lines += max(1, (length + chars_per_line - 1) // chars_per_line)
    return int(total_lines * size * 1.5) + 8


def element_bottom(el: dict[str, Any]) -> float:
    y = float(el.get("y", 0))
    if el.get("type") == "image":
        return y + float(el.get("height", 300))
    size = int(el.get("size", 16))
    return y + estimate_text_height(str(el.get("content", "")), size)


def board_bottom(board: list[dict[str, Any]]) -> float:
    if not board:
        return 0.0
    return max(element_bottom(el) for el in board)


def resolve_y(
    board: list[dict[str, Any]],
    requested_y: float,
    *,
    text: str = "",
    is_image: bool = False,
    height: int = 180,
) -> float:
    """Evita sobreposição: posiciona abaixo do conteúdo existente quando necessário."""
    if not board:
        return float(requested_y)
    gap = 24.0
    min_y = board_bottom(board) + gap
    resolved = max(float(requested_y), min_y)
    if is_image and text:
        # reserva espaço implícito se o modelo pediu y baixo com texto acima no board
        pass
    return resolved
