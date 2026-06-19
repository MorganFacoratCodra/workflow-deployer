import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ExecutionSocketManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, execution_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.connections[execution_id].add(websocket)

    async def disconnect(self, execution_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            if execution_id in self.connections and websocket in self.connections[execution_id]:
                self.connections[execution_id].remove(websocket)
                if not self.connections[execution_id]:
                    del self.connections[execution_id]

    async def broadcast(self, execution_id: int, payload: dict) -> None:
        async with self._lock:
            sockets = list(self.connections.get(execution_id, set()))
        stale: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(execution_id, websocket)


socket_manager = ExecutionSocketManager()
