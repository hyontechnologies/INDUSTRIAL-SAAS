"""
Piccadily Industrial Historian — WebSocket Broadcast Manager
Per-(tenant, plant) room management with dead socket cleanup.
"""

import asyncio
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import structlog
from fastapi import WebSocket

log = structlog.get_logger("historian.broadcaster")


class ConnectionManager:
    """
    Manages live WebSocket connections grouped by (tenant_id, plant_id).
    Lock is only held during set mutation, not during sends
    (eliminates head-of-line blocking on slow clients).
    Dead connections are evicted lazily after failed sends.
    """

    def __init__(self):
        self._connections: Dict[Tuple[str, str], Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, tenant_id: str, plant_id: str):
        await ws.accept()
        key = (tenant_id, plant_id)
        async with self._lock:
            self._connections[key].add(ws)
        log.info("ws.connect", tenant=tenant_id, plant=plant_id, room_size=len(self._connections[key]))

    async def disconnect(self, ws: WebSocket, tenant_id: str, plant_id: str):
        key = (tenant_id, plant_id)
        async with self._lock:
            self._connections[key].discard(ws)

    async def broadcast(self, tenant_id: str, plant_id: str, message: dict):
        """
        Broadcast to all clients in the room. Snapshot the set before sending
        so we don't hold the lock during I/O.
        """
        key = (tenant_id, plant_id)
        socks = list(self._connections.get(key, set()))
        dead: List[WebSocket] = []
        for ws in socks:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections[key].discard(ws)

    async def broadcast_tenant(self, tenant_id: str, message: dict):
        """Broadcast to ALL rooms of a tenant (e.g. alarm ACK where plant_id unknown)."""
        tasks = []
        for tid, pid in list(self._connections.keys()):
            if tid == tenant_id:
                tasks.append(self.broadcast(tid, pid, message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def connection_count(self) -> int:
        return sum(len(v) for v in self._connections.values())


# Singleton instance used across the application
ws_manager = ConnectionManager()
