"""Serviço das rotinas: CRUD validado, agendador (APScheduler), recuperação após o PC ligar e gatilhos.

O SQLite (``app.storage.routine_store``) é a única fonte da verdade. O ``BackgroundScheduler`` usa
``MemoryJobStore``: os jobs são recriados a partir do SQLite em ``start()`` e a cada alteração
(``sync_jobs``), então o agendamento sobrevive a reinícios sem guardar jobs em pickle.

Recuperação (tolerância ``catch_up_minutes``): ao iniciar, a última execução prevista que não
rodou com o PC desligado roda uma vez (gatilho ``catch_up``) se estiver dentro da tolerância;
o resto vira uma linha ``missed`` no histórico.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

from app.core import ui_events
from app.routines import triggers as trig
from app.routines.models import RoutineError, normalize_text, time_trigger, validate_routine
from app.routines.runner import RoutineBusy, RoutineRunner
from app.storage import routine_store as routine_store_module

SWEEP_SECONDS = 60
_WAKE_WORDS = ("jarvis", "ok jarvis", "ei jarvis", "oi jarvis")
_EDITABLE = ("name", "enabled", "steps", "triggers", "quiet", "catch_up_minutes")


class RoutineNotFound(KeyError):
    pass


class RoutineService:
    def __init__(self, runner: RoutineRunner | None = None, registry: Any = None) -> None:
        self.runner = runner or RoutineRunner()
        self._registry = registry
        self.scheduler: Any = None
        self._lock = threading.RLock()

    # ── dependências ──────────────────────────────────────────────────────────
    @property
    def registry(self) -> Any:
        return self._registry

    @registry.setter
    def registry(self, value: Any) -> None:
        self._registry = value
        self.runner.registry = value

    @staticmethod
    def store() -> Any:
        return routine_store_module.routine_store

    def _now(self) -> datetime:
        return datetime.now(trig.TZ)

    # ── leitura ───────────────────────────────────────────────────────────────
    def get(self, routine_id: str) -> dict[str, Any]:
        routine = self.store().get(routine_id)
        if routine is None:
            raise RoutineNotFound("Rotina não encontrada.")
        return routine

    def describe(self, routine: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        """Rotina com próxima execução e textos prontos para a janela e a ferramenta."""
        upcoming = trig.next_run(routine, now or self._now())
        return {
            **routine,
            "running": self.runner.is_running(routine["id"]),
            "next_run": upcoming.isoformat() if upcoming else None,
            "next_run_label": trig.describe_when(upcoming, now) if upcoming else ("desativada" if not routine.get("enabled") else "sem horário"),
            "trigger_labels": [trig.describe_trigger(item) for item in routine.get("triggers") or []],
        }

    def list_with_next(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or self._now()
        return [self.describe(routine, now) for routine in self.store().list()]

    def next_runs(self, limit: int = 10, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or self._now()
        items: list[dict[str, Any]] = []
        for routine in self.store().list():
            for moment in trig.next_runs(routine, now, limit):
                items.append({"routine_id": routine["id"], "name": routine["name"], "at": moment.isoformat(), "label": trig.describe_when(moment, now)})
        items.sort(key=lambda item: item["at"])
        return items[: max(1, limit)]

    def history(self, routine_id: str, limit: int = 50) -> list[dict[str, Any]]:
        self.get(routine_id)
        return self.store().history(routine_id, limit)

    # ── escrita ───────────────────────────────────────────────────────────────
    def _check_unique(self, fields: dict[str, Any], routine_id: str | None) -> None:
        mine = {(item["type"], item.get("phrase") or item.get("slash")) for item in fields["triggers"] if item["type"] in ("voice", "command")}
        if not mine:
            return
        for other in self.store().list():
            if other["id"] == routine_id:
                continue
            for item in other.get("triggers") or []:
                key = (item.get("type"), item.get("phrase") or item.get("slash"))
                if key in mine:
                    what = f'a frase "{key[1]}"' if key[0] == "voice" else f"o comando /{key[1]}"
                    raise RoutineError(f'A rotina "{other["name"]}" já usa {what}.')

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Cria; com ``run_now`` também executa agora. Devolve ``{routine, next_run, run_id}``."""
        fields = validate_routine(payload, self._registry)
        with self._lock:
            self._check_unique(fields, None)
            routine = self.store().create(fields)
        self._changed(routine["id"])
        run_id = None
        if payload.get("run_now") is True:
            run_id = self.run_now(routine["id"], trigger_kind="agent" if payload.get("_origin") == "agent" else "manual")
        described = self.describe(self.get(routine["id"]))
        return {"routine": described, "next_run": described["next_run"], "run_id": run_id}

    def update(self, routine_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Substitui os campos enviados; os não enviados ficam como estão."""
        current = self.get(routine_id)
        merged = {name: current.get(name) for name in _EDITABLE}
        merged.update({name: payload[name] for name in _EDITABLE if name in payload})
        if "quiet_hours" in payload and "quiet" not in payload:
            merged["quiet"] = payload["quiet_hours"]
        fields = validate_routine(merged, self._registry)
        with self._lock:
            self._check_unique(fields, routine_id)
            self.store().update(routine_id, fields)
        self._changed(routine_id)
        described = self.describe(self.get(routine_id))
        return {"routine": described, "next_run": described["next_run"]}

    def set_enabled(self, routine_id: str, enabled: bool) -> dict[str, Any]:
        self.get(routine_id)
        self.store().set_enabled(routine_id, bool(enabled))
        self._changed(routine_id)
        return self.describe(self.get(routine_id))

    def delete(self, routine_id: str) -> None:
        if not self.store().delete(routine_id):
            raise RoutineNotFound("Rotina não encontrada.")
        self._changed(routine_id)

    def run_now(self, routine_id: str, trigger_kind: str = "manual") -> str:
        """Executa agora ("Executar agora", voz, comando): ignora horário de silêncio e o estado ativo."""
        routine = self.get(routine_id)
        if self.runner.is_running(routine_id):
            raise RoutineBusy(f'A rotina "{routine["name"]}" já está em execução.')
        run_id = self.runner.start(routine, trigger_kind)
        if run_id is None:
            raise RoutineBusy(f'A rotina "{routine["name"]}" já está em execução.')
        return run_id

    def _changed(self, routine_id: str) -> None:
        try:
            self.sync_jobs()
        except Exception:
            pass
        ui_events.publish({"type": "routine_changed", "routine_id": routine_id})

    # ── gatilhos de voz e comando ─────────────────────────────────────────────
    def match_phrase(self, text: str) -> dict[str, Any] | None:
        """Rotina cuja frase de voz é exatamente o pedido (sem "Jarvis", acentos e pontuação)."""
        spoken = normalize_text(text)
        for wake in sorted(_WAKE_WORDS, key=len, reverse=True):
            if spoken.startswith(wake + " "):
                spoken = spoken[len(wake) + 1:]
                break
        if not spoken:
            return None
        for routine in self.store().list():
            if any(item.get("type") == "voice" and item.get("phrase") == spoken for item in routine.get("triggers") or []):
                return routine
        return None

    def command_triggers(self) -> list[dict[str, Any]]:
        return [
            {"routine_id": routine["id"], "name": routine["name"], "slash": item["slash"]}
            for routine in self.store().list() for item in routine.get("triggers") or [] if item.get("type") == "command"
        ]

    # ── agendador ─────────────────────────────────────────────────────────────
    def start(self, *, paused: bool = False, now: datetime | None = None) -> None:
        """Liga o agendador (app real, depois do painel). Marca interrompidas e recupera as perdidas."""
        from apscheduler.schedulers.background import BackgroundScheduler

        with self._lock:
            if self.scheduler is not None:
                return
            self.store().mark_interrupted()
            self.recover(now)
            scheduler = BackgroundScheduler(timezone=trig.TZ, job_defaults={"coalesce": True, "max_instances": 1})
            scheduler.add_job(self.sweep, "interval", seconds=SWEEP_SECONDS, id="routines:sweep", replace_existing=True)
            self.scheduler = scheduler
            self.sync_jobs()
            scheduler.start(paused=paused)

    def stop(self) -> None:
        with self._lock:
            scheduler, self.scheduler = self.scheduler, None
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass

    def sync_jobs(self) -> None:
        """Um job por rotina ativa com horário futuro; id do job = id da rotina."""
        scheduler = self.scheduler
        if scheduler is None:
            return
        with self._lock:
            wanted: dict[str, dict[str, Any]] = {}
            now = self._now()
            for routine in self.store().list():
                trigger = time_trigger(routine)
                if routine.get("enabled") and trigger and trig.next_run(routine, now) is not None:
                    wanted[routine["id"]] = routine
            for job in scheduler.get_jobs():
                if job.id.startswith("rt_") and job.id not in wanted:
                    scheduler.remove_job(job.id)
            for routine_id, routine in wanted.items():
                aps = trig.build_aps_trigger(time_trigger(routine), anchor=trig._anchor(routine))
                scheduler.add_job(
                    self._fire, aps, args=[routine_id], id=routine_id, replace_existing=True,
                    misfire_grace_time=max(1, int(routine.get("catch_up_minutes") or 0) * 60), coalesce=True,
                )

    def _fire(self, routine_id: str, trigger_kind: str = "schedule", scheduled_for: float | None = None) -> str | None:
        """Disparo de horário: respeita ativa e horário de silêncio; grava ``last_scheduled_for``."""
        routine = self.store().get(routine_id)
        if routine is None or not routine.get("enabled"):
            return None
        when = scheduled_for if scheduled_for is not None else time.time()
        self.store().set_last(routine_id, last_scheduled_for=when)
        if trig.in_quiet_hours(routine.get("quiet"), self._now()):
            self.store().add_run(routine_id, trigger_kind, status="skipped", scheduled_for=when, summary="Pulada: horário de silêncio.")
            ui_events.publish({"type": "routine_changed", "routine_id": routine_id})
            return None
        try:
            return self.runner.start(routine, trigger_kind, scheduled_for=when)
        except Exception:
            self.store().add_run(routine_id, trigger_kind, status="failed", scheduled_for=when, summary="Não foi possível iniciar a rotina.")
            return None

    def recover(self, now: datetime | None = None) -> list[str]:
        """Execuções perdidas com o PC desligado: a última dentro da tolerância roda; o resto vira ``missed``."""
        now = now or self._now()
        started: list[str] = []
        for routine in self.store().list():
            if not routine.get("enabled") or time_trigger(routine) is None:
                continue
            # Desde o último disparo ou a última edição (horário trocado não conta como perdido).
            since_stamp = max(float(value) for value in (routine.get("last_scheduled_for"), routine.get("updated_at"), routine.get("created_at")) if value)
            fires = trig.missed_fires(routine, trig.from_timestamp(since_stamp), now)
            if not fires:
                continue
            last = fires[-1]
            tolerance = int(routine.get("catch_up_minutes") or 0) * 60
            late = (now - last).total_seconds()
            missed = fires[:-1]
            if tolerance and late <= tolerance:
                run_id = self._fire(routine["id"], "catch_up", last.timestamp())
                if run_id:
                    started.append(run_id)
            else:
                missed = fires
                self.store().set_last(routine["id"], last_scheduled_for=last.timestamp())
            if missed:
                first = missed[0]
                summary = (f"Perdida com o PC desligado: {first:%d/%m %H:%M}." if len(missed) == 1 else
                           f"{len(missed)} execuções perdidas com o PC desligado (de {first:%d/%m %H:%M} a {missed[-1]:%d/%m %H:%M}).")
                self.store().add_run(routine["id"], "schedule", status="missed", scheduled_for=missed[-1].timestamp(), summary=summary)
                if not (tolerance and late <= tolerance):
                    self.store().set_last(routine["id"], last_status="missed", last_summary=summary)
        return started

    def sweep(self) -> None:
        """A cada 60 s, só com execução pausada: expira aprovações vencidas e fecha as órfãs."""
        if not any(execution.paused_action for execution in self.runner.active()):
            return
        try:
            from app.ui.panel.api.actions import sweep_expired_proposals
            sweep_expired_proposals()
        except Exception:
            pass
        self.runner.reconcile()


routine_service = RoutineService()
