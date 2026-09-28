"""Life OS Tool for Jarvis Agent.

Permite ao Jarvis consultar e atualizar o Life OS (Evolute) através de comandos
naturais de voz e chat: registro de água, hábitos, streaks, treinos e falas motivacionais.
"""
from __future__ import annotations

from typing import Any
from app.agent.tools.base import BaseTool, ToolResult
from app.services.lifeos import LifeOSService


class LifeOSTool(BaseTool):
    @property
    def name(self) -> str:
        return "lifeos_tool"

    @property
    def description(self) -> str:
        return (
            "Gerencia e consulta o Life OS / Evolute: registra consumo de água (ex: 500ml), "
            "marca hábitos concluídos (treino, foco, leitura), consulta sequências (streaks), "
            "registra treinos e solicita conselho motivacional de alta performance."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "add_water",
                        "get_water",
                        "check_habit",
                        "uncheck_habit",
                        "list_habits",
                        "log_workout",
                        "summary",
                        "motivate",
                    ],
                    "description": "Ação a ser executada no Life OS.",
                },
                "amount": {
                    "type": "number",
                    "description": "Quantidade numérica (ex: 500 para 500ml de água, 45 para 45min de estudo).",
                },
                "habit_name": {
                    "type": "string",
                    "description": "Nome ou palavra-chave do hábito (ex: 'treino', 'água', 'estudo', 'leitura', 'memória').",
                },
                "workout_name": {
                    "type": "string",
                    "description": "Nome do treino ou grupamento muscular (ex: 'Peito e Tríceps', 'Pernas').",
                },
                "notes": {
                    "type": "string",
                    "description": "Observações adicionais para o registro.",
                },
            },
            "required": ["action"],
        }

    def run(
        self,
        action: str = "summary",
        amount: float | None = None,
        habit_name: str = "",
        workout_name: str = "",
        notes: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        act = (action or "summary").lower().strip()

        # 1. Adicionar Água
        if act == "add_water":
            ml = int(amount or 250)
            if ml <= 0:
                ml = 250
            res = LifeOSService.add_water(ml)
            if res.get("ok"):
                msg = (
                    f"💧 Registrado {res['added_ml']}ml de água no Life OS. "
                    f"Total de hoje: {res['total_ml']}ml de {res['target_ml']}ml ({res['percentage']}% da meta)."
                )
                if res.get("habit_completed"):
                    msg += " 🎯 Meta diária de hidratação atingida! Hábito de água marcado."
                return {"ok": True, "message": msg, "data": res}
            return {"ok": False, "error": "Não foi possível registrar o consumo de água."}

        # 2. Consultar Água
        if act == "get_water":
            s = LifeOSService.get_daily_summary()
            w = s.get("water", {})
            return {
                "ok": True,
                "message": f"💧 Consumo atual: {w.get('current_ml', 0)}ml de {w.get('target_ml', 3000)}ml ({w.get('percentage', 0)}% da meta).",
                "data": w,
            }

        # 3. Marcar Hábito como Concluído
        if act in ("check_habit", "check"):
            target = habit_name or "treino"
            res = LifeOSService.toggle_habit(target, completed=True)
            if res.get("ok"):
                msg = (
                    f"✅ Hábito '{res['title']}' marcado como concluído no Life OS! "
                    f"Sequência atual: {res['streak']} dias seguidos (Recorde: {res['bestStreak']} dias). Excelente disciplina, Sir!"
                )
                return {"ok": True, "message": msg, "data": res}
            return {"ok": False, "error": res.get("error", "Hábito não encontrado.")}

        # 4. Desmarcar Hábito
        if act in ("uncheck_habit", "uncheck"):
            target = habit_name or "treino"
            res = LifeOSService.toggle_habit(target, completed=False)
            if res.get("ok"):
                msg = f"Hábito '{res['title']}' desmarcado no Life OS. Streak ajustado para {res['streak']} dias."
                return {"ok": True, "message": msg, "data": res}
            return {"ok": False, "error": res.get("error", "Hábito não encontrado.")}

        # 5. Listar Hábitos
        if act == "list_habits":
            s = LifeOSService.get_daily_summary()
            items = s.get("habits", {}).get("items", [])
            lines = [f"📋 Hábitos no Life OS ({s['habits']['completed']}/{s['habits']['total']} concluídos hoje):"]
            for h in items:
                status = "✅" if h.get("completed_today") else "○"
                lines.append(f"{status} {h.get('title')} — 🔥 {h.get('streak')} dias")
            return {"ok": True, "message": "\n".join(lines), "data": items}

        # 6. Registrar Treino
        if act == "log_workout":
            name = workout_name or "Treino com Sobrecarga"
            res = LifeOSService.log_workout(name)
            return {
                "ok": True,
                "message": f"🏋️ Treino '{name}' registrado com sucesso no Life OS! Hábito de treino diário marcado.",
                "data": res,
            }

        # 7. Fala Motivacional
        if act == "motivate":
            s = LifeOSService.get_daily_summary()
            speech = s.get("motivational", {}).get("speech", "")
            return {
                "ok": True,
                "message": f"💡 Palavra do Jarvis:\n{speech}",
                "data": s.get("motivational"),
            }

        # 8. Resumo Geral
        s = LifeOSService.get_daily_summary()
        w = s.get("water", {})
        h = s.get("habits", {})
        workout = s.get("workout", {})
        msg = (
            f"⚡ Resumo Life OS de Hoje ({s.get('date')}):\n"
            f"- Hidratação: {w.get('current_ml', 0)} / {w.get('target_ml', 3000)} ml ({w.get('percentage', 0)}%)\n"
            f"- Hábitos: {h.get('completed', 0)} de {h.get('total', 0)} concluídos ({h.get('rate_percentage', 0)}%)\n"
            f"- Treino: {workout.get('split_name', 'Treino Geral')} ({'Concluído ✅' if workout.get('completed') else 'Pendente'})\n"
            f"- Estudos: {s.get('study', {}).get('minutes_today', 0)} minutos registrados"
        )
        return {"ok": True, "message": msg, "data": s}
