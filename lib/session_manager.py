"""Shared websocket session lifecycle helpers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


@dataclass
class Session:
    id: str
    target: str
    state: str = "active"


class SessionManager:
    """Maintain lightweight session state for websocket-backed streams."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    def create_session(self, session_id: str, target: str) -> Session:
        session = Session(id=session_id, target=target)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.state = "closed"

    async def handle_websocket(
        self,
        websocket: WebSocket,
        session_id: str,
        read_cb: Callable[[bytes], Any],
        write_cb: Callable[[], AsyncIterator[bytes]],
    ) -> None:
        await websocket.accept()

        async def _reader() -> None:
            while True:
                try:
                    payload = await websocket.receive_bytes()
                except WebSocketDisconnect:
                    break
                read_cb(payload)

        async def _writer() -> None:
            async for payload in write_cb():
                await websocket.send_bytes(payload)

        try:
            await asyncio.gather(_reader(), _writer())
        finally:
            async with self._lock:
                self.close_session(session_id)
