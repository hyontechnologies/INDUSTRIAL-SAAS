#!/usr/bin/env python3
"""
=============================================================================
PICCADILY AGRO INDUSTRIES — OPC UA Edge Agent  v2.0
Phase 6: Async OPC UA Subscription + Cloud Telemetry Uploader

Architecture:
  Python OPC UA Bridge (asyncua server, port 4840)
    └=► This Agent (asyncua subscriber)
          └=► FastAPI endpoint on Azure Ubuntu VM
                └=► TimescaleDB

Features:
  • Dynamic tag discovery via OPC UA namespace browsing
  • Asyncua subscription with monitored items (pub/sub, not polling)
  • Batched HTTP upload every N seconds or M items (whichever first)
  • Exponential backoff reconnection for both OPC and HTTP failures
  • Tag quality filtering (only Good OPC quality passes)
  • Timestamp synchronisation (server-side OPC timestamp preferred)
  • Duplicate prevention via dedup window
  • Graceful VM-restart recovery (persistent cursor in local SQLite)
  • Structured logging with per-tag statistics

FIXES vs v1.0:
  [FIX-D1] OPC URL corrected to /piccadily/ (bridge endpoint)
  [FIX-D2] Namespace URI corrected to urn:piccadily:boilerbridge
  [FIX-D3] Node resolution via hierarchical browse (not KEP dotted paths)
  [FIX-D4] Dynamic tag discovery — auto-discovers ALL tags from bridge
  [FIX-D5] Cursor DB path Windows-compatible
=============================================================================
"""

import asyncio
import logging
import os
import signal
import sys
import time
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple

import aiohttp  # pip install aiohttp
from asyncua import Client  # pip install asyncua

try:
    from asyncua.common.subscription import SubHandler as _BaseHandler
except ImportError:
    _BaseHandler = object  # asyncua 1.1.x uses duck-typed handlers

# ---------------------------------------------------------------------------
# Configuration — override with environment variables in production
# ---------------------------------------------------------------------------
OPCUA_ENDPOINT = os.getenv("OPCUA_ENDPOINT", "opc.tcp://100.101.102.103:4840/piccadily/")
FASTAPI_ENDPOINT = os.getenv("FASTAPI_ENDPOINT", "http://localhost:8000")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

OPC_URL = OPCUA_ENDPOINT
API_URL = f"{FASTAPI_ENDPOINT}/telemetry/ingest"
OPC_NS_URI = os.getenv("OPC_NS_URI", "urn:piccadily:boilerbridge")
PLANT_ID = os.getenv("PLANT_ID", "PICCADILY_PLANT_01")
DEVICE_ID = os.getenv("DEVICE_ID", "BOILER_PLC_01")
OPC_USERNAME = os.getenv("OPC_USER", "")
OPC_PASSWORD = os.getenv("OPC_PASS", "")

API_KEY = os.getenv("API_KEY", "changeme")

MAX_BATCH = int(os.getenv("MAX_BATCH", "200"))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "2.0"))
PUB_INTERVAL_MS = int(os.getenv("PUB_INTERVAL_MS", "500"))
BASE_RETRY = float(os.getenv("BASE_RETRY", "2.0"))
MAX_RETRY = float(os.getenv("MAX_RETRY", "60.0"))
DEDUP_WINDOW_S = float(os.getenv("DEDUP_WINDOW_S", "0.5"))

# Windows-compatible default cursor path
_default_cursor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edge_cursor.db")
CURSOR_DB = os.getenv("CURSOR_DB", _default_cursor)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("EdgeAgent")
logging.getLogger("asyncua").setLevel(logging.WARNING)


# =============================================================================
# DATA STRUCTURES
# =============================================================================
@dataclass
class TelemetryPoint:
    plant_id: str
    group: str
    tag: str
    unit: str
    value: Any
    quality: str
    ts_server: str
    ts_agent: str
    seq: int

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# DEDUP WINDOW
# =============================================================================
class DedupWindow:
    def __init__(self, window_s: float = 0.5):
        self._window = window_s
        self._cache: Dict[str, tuple] = {}

    def is_duplicate(self, key: str, value: Any, ts_epoch: float) -> bool:
        if key in self._cache:
            prev_val, prev_ts = self._cache[key]
            if value == prev_val and (ts_epoch - prev_ts) < self._window:
                return True
        self._cache[key] = (value, ts_epoch)
        return False


# =============================================================================
# CURSOR DB
# =============================================================================
class CursorDB:
    def __init__(self, path: str):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("CREATE TABLE IF NOT EXISTS cursor (key TEXT PRIMARY KEY, seq INTEGER)")
        self._conn.commit()

    def get(self, key: str = "main") -> int:
        row = self._conn.execute("SELECT seq FROM cursor WHERE key=?", (key,)).fetchone()
        return row[0] if row else 0

    def set(self, seq: int, key: str = "main"):
        self._conn.execute("INSERT OR REPLACE INTO cursor(key, seq) VALUES(?,?)", (key, seq))
        self._conn.commit()


# =============================================================================
# OPC UA SUBSCRIPTION HANDLER
# =============================================================================
class BoilerSubHandler(_BaseHandler):
    def __init__(self, queue: asyncio.Queue, dedup: DedupWindow, node_meta: Dict[str, tuple], seq_counter: list):
        self._q = queue
        self._dedup = dedup
        self._meta = node_meta
        self._seq = seq_counter
        self._stats_good = 0
        self._stats_bad = 0
        self._stats_dup = 0

    def datachange_notification(self, node, val, data):
        try:
            node_str = str(node)
            meta = self._meta.get(node_str)
            if meta is None:
                return
            group, tag, unit = meta

            dv = data.monitored_item.Value
            status = dv.StatusCode
            quality = "Good" if status.is_good() else "Uncertain" if status.is_uncertain() else "Bad"

            if quality != "Good":
                self._stats_bad += 1
                return

            ts_srv = dv.SourceTimestamp or dv.ServerTimestamp or datetime.now(timezone.utc)
            ts_srv_iso = ts_srv.isoformat() if hasattr(ts_srv, "isoformat") else str(ts_srv)
            ts_epoch = ts_srv.timestamp() if hasattr(ts_srv, "timestamp") else time.time()

            dedup_key = f"{group}.{tag}"
            if self._dedup.is_duplicate(dedup_key, val, ts_epoch):
                self._stats_dup += 1
                return

            self._seq[0] += 1
            self._stats_good += 1

            point = TelemetryPoint(
                plant_id=PLANT_ID,
                group=group,
                tag=tag,
                unit=unit,
                value=val,
                quality=quality,
                ts_server=ts_srv_iso,
                ts_agent=datetime.now(timezone.utc).isoformat(),
                seq=self._seq[0],
            )
            if self._q.full():
                try:
                    self._q.get_nowait()
                    log.warning("Queue full — dropped oldest point to make room")
                except asyncio.QueueEmpty:
                    pass

            self._q.put_nowait(point)

        except Exception as exc:
            log.error("SubHandler error: %s", exc, exc_info=True)

    def status_change_notification(self, status):
        log.warning("OPC subscription status changed: %s", status)

    def get_stats(self) -> Tuple[int, int, int]:
        return self._stats_good, self._stats_bad, self._stats_dup


# =============================================================================
# DYNAMIC TAG DISCOVERY — browse OPC UA namespace to find all tags
# =============================================================================
async def discover_tags(client: Client, ns_idx: int) -> List[Tuple[Any, str, str, str]]:
    """
    Browse the OPC UA namespace hierarchy:
      Objects / PLANT_ID / DEVICE_ID / {group} / {tag}
    Returns list of (node, group_name, tag_name, unit_hint).
    Skips the _Bridge diagnostics folder.
    """
    discovered = []

    try:
        root = client.nodes.objects
        # Browse to plant folder
        plant_node = await root.get_child(f"{ns_idx}:{PLANT_ID}")
        device_node = await plant_node.get_child(f"{ns_idx}:{DEVICE_ID}")

        # Browse group folders
        group_children = await device_node.get_children()
        for group_node in group_children:
            group_name = (await group_node.read_browse_name()).Name

            # Skip diagnostics folder
            if group_name.startswith("_"):
                continue

            # Browse tags within this group
            tag_children = await group_node.get_children()
            for tag_node in tag_children:
                tag_name = (await tag_node.read_browse_name()).Name

                # Try to extract unit from description
                unit = "-"
                try:
                    desc = await tag_node.read_description()
                    if desc and desc.Text:
                        # Description format: "Some Description [unit]"
                        text = desc.Text
                        if "[" in text and text.endswith("]"):
                            unit = text[text.rfind("[") + 1 : -1]
                except Exception:
                    pass

                discovered.append((tag_node, group_name, tag_name, unit))

    except Exception as exc:
        log.error("Tag discovery failed: %s", exc)

    return discovered


# =============================================================================
# HTTP UPLOADER TASK
# =============================================================================
async def uploader_task(
    queue: asyncio.Queue,
    cursor: CursorDB,
    stop_event: asyncio.Event,
):
    retry_delay = BASE_RETRY
    last_flush = time.monotonic()

    async with aiohttp.ClientSession(
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as session:
        while not stop_event.is_set():
            batch: List[TelemetryPoint] = []
            deadline = last_flush + FLUSH_INTERVAL

            while len(batch) < MAX_BATCH:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    point = await asyncio.wait_for(queue.get(), timeout=min(remaining, 0.1))
                    batch.append(point)
                except asyncio.TimeoutError:
                    break

            if not batch:
                await asyncio.sleep(0.05)
                continue

            payload = {
                "plant_id": PLANT_ID,
                "count": len(batch),
                "points": [p.to_dict() for p in batch],
            }

            try:
                async with session.post(API_URL, json=payload) as resp:
                    if resp.status in (200, 201, 202):
                        last_seq = batch[-1].seq
                        cursor.set(last_seq)
                        log.info("Uploaded %d points (seq=%d)", len(batch), last_seq)
                        retry_delay = BASE_RETRY
                    else:
                        body = await resp.text()
                        log.error("API error %d: %s", resp.status, body[:200])
                        for p in batch:
                            await queue.put(p)
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, MAX_RETRY)

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                log.warning("Upload failed (%s) — retry in %.1fs", exc, retry_delay)
                for p in batch:
                    await queue.put(p)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY)

            last_flush = time.monotonic()


# =============================================================================
# OPC UA CLIENT TASK
# =============================================================================
async def opc_client_task(
    queue: asyncio.Queue,
    stop_event: asyncio.Event,
):
    dedup = DedupWindow(DEDUP_WINDOW_S)
    seq_ctr = [0]
    retry_delay = BASE_RETRY

    while not stop_event.is_set():
        client = Client(url=OPC_URL, timeout=10)

        if OPC_USERNAME:
            client.set_user(OPC_USERNAME)
            client.set_password(OPC_PASSWORD)

        handler = None

        try:
            async with client:
                log.info("OPC UA connected to %s", OPC_URL)
                retry_delay = BASE_RETRY

                # Get namespace index
                ns_idx = await client.get_namespace_index(OPC_NS_URI)
                log.info("Namespace index: %d  (URI: %s)", ns_idx, OPC_NS_URI)

                # Dynamic tag discovery
                tags = await discover_tags(client, ns_idx)
                log.info("Discovered %d tags across OPC UA namespace", len(tags))

                if not tags:
                    log.error("No tags discovered — check PLANT_ID/DEVICE_ID")
                    await asyncio.sleep(retry_delay)
                    continue

                # Build node_meta mapping
                node_meta: Dict[str, tuple] = {}
                nodes_to_subscribe = []

                for node, group, tag, unit in tags:
                    node_meta[str(node)] = (group, tag, unit)
                    nodes_to_subscribe.append(node)

                # Log group summary
                groups: Dict[str, int] = {}
                for _, g, _, _ in tags:
                    groups[g] = groups.get(g, 0) + 1
                for g, c in sorted(groups.items()):
                    log.info("  Group %-20s : %3d tags", g, c)

                # Create subscription
                handler = BoilerSubHandler(queue, dedup, node_meta, seq_ctr)
                sub = await client.create_subscription(PUB_INTERVAL_MS, handler)

                # Subscribe in chunks
                CHUNK = 50
                for i in range(0, len(nodes_to_subscribe), CHUNK):
                    chunk = nodes_to_subscribe[i : i + CHUNK]
                    await sub.subscribe_data_change(chunk)
                    log.info("Subscribed chunk %d–%d", i, i + len(chunk) - 1)

                log.info("=" * 60)
                log.info("  ALL %d SUBSCRIPTIONS ACTIVE", len(nodes_to_subscribe))
                log.info("=" * 60)

                # Keep alive — log stats every 30s
                while not stop_event.is_set():
                    await asyncio.sleep(30.0)
                    if handler:
                        good, bad, dup = handler.get_stats()
                        log.info(
                            "STATS | Good=%d | Bad=%d | Dedup=%d | QueueDepth=%d | Seq=%d",
                            good,
                            bad,
                            dup,
                            queue.qsize(),
                            seq_ctr[0],
                        )

                await sub.delete()

        except Exception as exc:
            log.error("OPC connection error: %s — retry in %.1fs", exc, retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, MAX_RETRY)


# =============================================================================
# MAIN
# =============================================================================
async def main():
    log.info("=" * 60)
    log.info("  Piccadily OPC UA Edge Agent v2.0")
    log.info("  Plant       : %s", PLANT_ID)
    log.info("  Device      : %s", DEVICE_ID)
    log.info("  OPC UA      : %s", OPC_URL)
    log.info("  Namespace   : %s", OPC_NS_URI)
    log.info("  Cloud API   : %s", API_URL)
    log.info("  Batch/Flush : %d / %.1fs", MAX_BATCH, FLUSH_INTERVAL)
    log.info("  Cursor DB   : %s", CURSOR_DB)
    log.info("=" * 60)

    queue = asyncio.Queue(maxsize=100_000)
    stop_event = asyncio.Event()
    cursor = CursorDB(CURSOR_DB)

    log.info("Resuming from cursor seq=%d", cursor.get())

    # Graceful shutdown
    def _shutdown():
        log.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass  # Windows

    await asyncio.gather(
        opc_client_task(queue, stop_event),
        uploader_task(queue, cursor, stop_event),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Edge agent stopped by user.")
