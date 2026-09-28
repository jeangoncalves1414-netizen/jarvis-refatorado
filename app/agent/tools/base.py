from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.actions import ToolMetadata


@dataclass(slots=True)
class ToolResult:
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


class Tool(Protocol):
    name: str
    description: str
    critical: bool
    metadata: ToolMetadata

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        ...


class BaseTool:
    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def description(self) -> str:
        return ""

    @property
    def critical(self) -> bool:
        return False

    @property
    def metadata(self) -> ToolMetadata:
        """Declarative safety contract used by the Action Kernel.

        Legacy tools remain compatible: a previously ``critical`` tool is
        conservatively treated as critical until it declares richer metadata.
        """
        return ToolMetadata(
            capabilities=(self.name,),
            default_risk="critical" if self.critical else "low",
            requires_confirmation=self.critical,
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {}

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Implementação simplificada. Ferramentas podem sobrescrever run() em vez de execute()."""
        raise NotImplementedError

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        """Bridge padrão: tenta chamar run(**args) e converte o resultado para ToolResult.
        Ferramentas podem sobrescrever execute() diretamente para controle total."""
        try:
            result = self.run(**(args or {}))
            if isinstance(result, dict):
                ok = result.get("success", result.get("ok", True))
                msg = result.get("message", result.get("extracted_text", result.get("error", str(result))))
                data = {k: v for k, v in result.items() if k not in ("success", "ok", "message", "error")}
                return ToolResult(ok=bool(ok), message=str(msg), data=data)
            return ToolResult(ok=True, message=str(result))
        except NotImplementedError:
            raise
        except Exception as exc:
            return ToolResult(ok=False, message=f"Erro ao executar {getattr(self, 'name', type(self).__name__)}: {exc}")
