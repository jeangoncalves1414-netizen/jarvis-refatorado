"""Cliente MCP para conexão local stdio via biblioteca oficial mcp."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """Wrapper assíncrono e síncrono para conexão com servidor MCP via stdio."""

    def __init__(
        self,
        server_id: str,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.server_id = server_id
        self.name = name
        self.command = command
        self.args = list(args or [])
        self.env = dict(env or {})

        self.status: str = "offline"  # online, offline, error, connecting
        self.last_error: str = ""
        self.tools: list[dict[str, Any]] = []

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._queue: asyncio.Queue[tuple[str, Any, asyncio.Future[Any]] | None] | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._lock = threading.Lock()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or not self._loop.is_running():
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(
                    target=self._loop.run_forever,
                    daemon=True,
                    name=f"MCPClient-{self.server_id}",
                )
                self._thread.start()
            return self._loop

    async def _worker(self, ready_event: asyncio.Event, err_holder: list[Exception]) -> None:
        try:
            full_env = {**os.environ, **self.env}
            params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=full_env,
            )
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    list_res = await session.list_tools()
                    self.tools = [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": (
                                t.inputSchema.model_dump()
                                if hasattr(t.inputSchema, "model_dump")
                                else getattr(t, "inputSchema", {})
                            ),
                        }
                        for t in list_res.tools
                    ]
                    self.status = "online"
                    self.last_error = ""
                    ready_event.set()

                    queue = self._queue
                    if queue is None:
                        return

                    while True:
                        item = await queue.get()
                        if item is None:
                            break
                        action, req_args, fut = item
                        try:
                            if action == "list_tools":
                                res = await session.list_tools()
                                parsed = [
                                    {
                                        "name": t.name,
                                        "description": t.description or "",
                                        "parameters": (
                                            t.inputSchema.model_dump()
                                            if hasattr(t.inputSchema, "model_dump")
                                            else getattr(t, "inputSchema", {})
                                        ),
                                    }
                                    for t in res.tools
                                ]
                                self.tools = parsed
                                fut.set_result(parsed)
                            elif action == "call_tool":
                                tool_name, arguments = req_args
                                call_res = await session.call_tool(tool_name, arguments or {})
                                fut.set_result(call_res)
                            else:
                                fut.set_exception(ValueError(f"Ação desconhecida: {action}"))
                        except Exception as exc:
                            fut.set_exception(exc)
        except Exception as exc:
            self.status = "error"
            self.last_error = str(exc)
            err_holder.append(exc)
            if not ready_event.is_set():
                ready_event.set()
        finally:
            if self.status != "error":
                self.status = "offline"

    async def connect_async(self, timeout: float = 15.0) -> bool:
        loop = asyncio.get_running_loop()
        self.status = "connecting"
        self._queue = asyncio.Queue()
        ready_event = asyncio.Event()
        err_holder: list[Exception] = []

        self._worker_task = loop.create_task(self._worker(ready_event, err_holder))
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.status = "error"
            self.last_error = f"Timeout ({timeout}s) ao inicializar servidor MCP."
            await self.disconnect_async()
            raise TimeoutError(self.last_error)

        if err_holder:
            raise err_holder[0]
        return True

    def connect(self, timeout: float = 15.0) -> bool:
        """Conecta síncronamente ao servidor MCP."""
        loop = self._ensure_loop()

        async def _do_connect() -> bool:
            self.status = "connecting"
            self._queue = asyncio.Queue()
            ready_event = asyncio.Event()
            err_holder: list[Exception] = []
            self._worker_task = asyncio.create_task(self._worker(ready_event, err_holder))
            try:
                await asyncio.wait_for(ready_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                self.status = "error"
                self.last_error = f"Timeout ({timeout}s) ao inicializar servidor MCP."
                if self._queue:
                    await self._queue.put(None)
                raise TimeoutError(self.last_error)

            if err_holder:
                raise err_holder[0]
            return True

        fut = asyncio.run_coroutine_threadsafe(_do_connect(), loop)
        return fut.result(timeout=timeout + 2.0)

    async def list_tools_async(self, timeout: float = 10.0) -> list[dict[str, Any]]:
        if self._queue is None or self.status != "online":
            raise RuntimeError(f"Servidor '{self.name}' não está conectado.")
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        await self._queue.put(("list_tools", None, fut))
        res = await asyncio.wait_for(fut, timeout=timeout)
        return res

    def list_tools(self, timeout: float = 10.0) -> list[dict[str, Any]]:
        """Lista ferramentas de forma síncrona."""
        if self._queue is None or self.status != "online" or self._loop is None:
            return self.tools

        async def _do() -> list[dict[str, Any]]:
            loop = asyncio.get_running_loop()
            fut: asyncio.Future[Any] = loop.create_future()
            if self._queue:
                await self._queue.put(("list_tools", None, fut))
            return await fut

        fut = asyncio.run_coroutine_threadsafe(_do(), self._loop)
        return fut.result(timeout=timeout)

    async def call_tool_async(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> Any:
        if self._queue is None or self.status != "online":
            raise RuntimeError(f"Servidor '{self.name}' não está online.")
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        await self._queue.put(("call_tool", (tool_name, arguments or {}), fut))
        res = await asyncio.wait_for(fut, timeout=timeout)
        return res

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """Invoca uma ferramenta MCP de forma síncrona."""
        if self._queue is None or self.status != "online" or self._loop is None:
            raise RuntimeError(f"Servidor '{self.name}' não está online (status={self.status}).")

        async def _do() -> Any:
            loop = asyncio.get_running_loop()
            fut: asyncio.Future[Any] = loop.create_future()
            if self._queue:
                await self._queue.put(("call_tool", (tool_name, arguments or {}), fut))
            return await fut

        fut = asyncio.run_coroutine_threadsafe(_do(), self._loop)
        return fut.result(timeout=timeout)

    async def disconnect_async(self, timeout: float = 5.0) -> None:
        self.status = "offline"
        if self._queue is not None:
            try:
                await self._queue.put(None)
            except Exception:
                pass
        if self._worker_task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self._worker_task), timeout=timeout)
            except Exception:
                self._worker_task.cancel()
        self._queue = None
        self._worker_task = None

    def disconnect(self, timeout: float = 5.0) -> None:
        """Desconecta de forma síncrona."""
        if self._loop and self._loop.is_running():
            async def _stop() -> None:
                await self.disconnect_async(timeout=timeout)

            try:
                fut = asyncio.run_coroutine_threadsafe(_stop(), self._loop)
                fut.result(timeout=timeout + 2.0)
            except Exception:
                pass
        self.status = "offline"
