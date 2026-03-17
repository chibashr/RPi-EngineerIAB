from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect


@dataclass
class Session:
    id: str
    target: Any
    state: str = "open"


ReadCallback = Callable[[bytes], None]
WriteCallback = Callable[[], AsyncIterator[bytes]]


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create_session(self, session_id: str, target: Any) -> Session:
        session = Session(id=session_id, target=target, state="open")
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.state = "closed"
            del self._sessions[session_id]

    def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())

    async def handle_websocket(
        self,
        websocket: WebSocket,
        session_id: str,
        read_cb: ReadCallback,
        write_cb: WriteCallback,
    ) -> None:
        await websocket.accept()

        session = self.get_session(session_id)
        if session is None or session.state != "open":
            await websocket.close(code=1000)
            return

        write_iter = write_cb()

        async def _reader() -> None:
            try:
                while True:
                    message = await websocket.receive()
                    if "bytes" in message and message["bytes"] is not None:
                        read_cb(message["bytes"])
                    elif "text" in message and message["text"] is not None:
                        read_cb(message["text"].encode("utf-8"))
            except WebSocketDisconnect:
                self.close_session(session_id)
            except RuntimeError:
                self.close_session(session_id)

        async def _writer() -> None:
            try:
                async for chunk in write_iter:
                    await websocket.send_bytes(chunk)
            except WebSocketDisconnect:
                self.close_session(session_id)

        try:
            await self._run_reader_writer(_reader, _writer)
        finally:
            if self.get_session(session_id) is not None:
                self.close_session(session_id)

    async def _run_reader_writer(
        self,
        reader: Callable[[], Awaitable[None]],
        writer: Callable[[], Awaitable[None]],
    ) -> None:
        from asyncio import Task, create_task, gather

        reader_task: Task[None] = create_task(reader())
        writer_task: Task[None] = create_task(writer())

        try:
            await gather(reader_task, writer_task)
        finally:
            if not reader_task.done():
                reader_task.cancel()
            if not writer_task.done():
                writer_task.cancel()
