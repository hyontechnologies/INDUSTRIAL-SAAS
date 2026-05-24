"""
Industrial Operations Cloud — WebSocket Broadcast Manager
Per-(tenant, plant) room management with parallel fanout and dead socket cleanup.
"""

import json
import asyncio
from collections import defaultdict
from typing import Dict, Set, Tuple

import structlog
from fastapi import WebSocket

from app.infra.redis import get_redis
from app.core.redis_keys import ws_broadcast_channel

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
        self._pubsub_task: asyncio.Task | None = None

    async def start_pubsub(self):
        """Start background task to listen for Redis Pub/Sub broadcasts."""
        if not get_redis():
            return
        pubsub = get_redis().pubsub()
        await pubsub.psubscribe("ws|broadcast|*")
        self._pubsub_task = asyncio.create_task(self._listen_to_redis(pubsub))
        log.info("ws.pubsub_started")

    async def _listen_to_redis(self, pubsub):
        try:
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"]
                    data = json.loads(message["data"])

                    # Extract tenant/plant from channel name "ws|broadcast|tenant_id|plant_id"
                    parts = channel.split("|")
                    if len(parts) == 4:
                        tenant_id, plant_id = parts[2], parts[3]
                        await self._local_fanout(tenant_id, plant_id, data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error("ws.pubsub_error", error=str(e))

    async def stop_pubsub(self):
        if self._pubsub_task:
            self._pubsub_task.cancel()

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
        Publish message to Redis Pub/Sub for all workers to receive.
        """
        if get_redis():
            channel = ws_broadcast_channel(tenant_id, plant_id)
            await get_redis().publish(channel, json.dumps(message))
        else:
            # Fallback to local if redis not initialized
            await self._local_fanout(tenant_id, plant_id, message)

    async def _local_fanout(self, tenant_id: str, plant_id: str, message: dict):
        """
        Broadcast to all local clients in the room using parallel sends.
        One slow client no longer blocks others.
        """
        key = (tenant_id, plant_id)
        socks = list(self._connections.get(key, set()))
        if not socks:
            return

        async def _safe_send(ws: WebSocket) -> WebSocket | None:
            try:
                await ws.send_json(message)
                return None
            except Exception:
                return ws

        results = await asyncio.gather(*[_safe_send(ws) for ws in socks], return_exceptions=True)
        dead = [ws for ws in results if isinstance(ws, WebSocket)]
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
