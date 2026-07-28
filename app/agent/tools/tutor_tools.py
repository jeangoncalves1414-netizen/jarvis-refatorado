from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class TutorSaveProgressTool(BaseTool):
    def __init__(self, tutor_store: Any) -> None:
        self._store = tutor_store

    @property
    def name(self) -> str:
        return "tutor_save_progress"

    @property
    def description(self) -> str:
        return "Registra progresso de estudo ENEM: etapa, conceito dominado, resumo de sessão ou questão resolvida."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "stage_id": {"type": "string", "description": "ID da etapa ENEM (ex: 04-matematica)."},
                "concept": {"type": "string", "description": "Conceito trabalhado nesta sessão."},
                "mastered": {"type": "boolean", "description": "Se o aluno dominou o conceito."},
                "session_summary": {"type": "string", "description": "Resumo curto do que foi ensinado."},
                "question_solved": {"type": "boolean", "description": "Se uma questão ENEM foi resolvida."},
            },
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        self._store.save_progress(
            stage_id=args.get("stage_id"),
            concept=args.get("concept"),
            mastered=bool(args.get("mastered")),
            session_summary=args.get("session_summary"),
            question_solved=bool(args.get("question_solved")),
        )
        if args.get("concept") and not args.get("mastered"):
            self._store.add_weak_spot(str(args["concept"]))
        return ToolResult(ok=True, message="Progresso de estudo registrado.", data=args)


class TutorAddFlashcardTool(BaseTool):
    def __init__(self, tutor_store: Any) -> None:
        self._store = tutor_store

    @property
    def name(self) -> str:
        return "tutor_add_flashcard"

    @property
    def description(self) -> str:
        return "Cria um flashcard para revisão espaçada de um conceito ENEM."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "front": {"type": "string", "description": "Pergunta ou prompt do flashcard."},
                "back": {"type": "string", "description": "Resposta ou explicação."},
                "topic": {"type": "string", "description": "Tópico específico."},
                "stage": {"type": "string", "description": "Etapa ENEM associada."},
            },
            "required": ["front", "back"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        self._store.add_flashcard(
            front=str(args.get("front", "")),
            back=str(args.get("back", "")),
            topic=str(args.get("topic", "")),
            stage=str(args.get("stage", "")),
        )
        return ToolResult(ok=True, message=f"Flashcard criado: {args.get('front', '')[:40]}", data=args)


class TutorSaveFeynmanTool(BaseTool):
    def __init__(self, tutor_store: Any) -> None:
        self._store = tutor_store

    @property
    def name(self) -> str:
        return "tutor_save_feynman"

    @property
    def description(self) -> str:
        return "Registra avaliação Feynman: nota, feedback e explicação do aluno."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Tópico explicado pelo aluno."},
                "explanation": {"type": "string", "description": "Resumo da explicação do aluno."},
                "grade": {"type": "integer", "description": "Nota de 1 a 5."},
                "feedback": {"type": "string", "description": "Análise de lacunas e pontos fortes."},
            },
            "required": ["topic", "grade", "feedback"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        attempt_id = self._store.add_feynman_attempt(
            topic=str(args.get("topic", "")),
            explanation=str(args.get("explanation", "")),
            grade=int(args.get("grade", 3)),
            feedback=str(args.get("feedback", "")),
        )
        return ToolResult(ok=True, message="Avaliação Feynman registrada.", data={"id": attempt_id})


class EnemSaveQuestionTool(BaseTool):
    def __init__(self, enem_store: Any) -> None:
        self._store = enem_store

    @property
    def name(self) -> str:
        return "enem_save_question"

    @property
    def description(self) -> str:
        return "Salva uma questão ENEM colada pelo aluno no banco local para referência futura."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto completo da questão."},
                "subject": {"type": "string", "description": "Área: linguagens, humanas, natureza, matematica, redacao."},
                "area": {"type": "string", "description": "Alias de subject."},
                "year": {"type": "integer", "description": "Ano da prova ENEM."},
            },
            "required": ["text"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        question = self._store.save_question({
            "text": str(args.get("text", "")),
            "subject": str(args.get("subject") or args.get("area", "")),
            "year": args.get("year"),
            "source": "agent",
        })
        return ToolResult(
            ok=True,
            message=f"Questão salva (id: {question['id']})",
            data={"id": question["id"], "path": str(question.get("id", ""))},
        )
