#!/usr/bin/env python3
"""
=============================================================================
=============================================================================
INDUSTRIAL OPERATIONS CLOUD — OPC UA Edge Agent v3.0
Continuous subscription agent with SQLite state storage and batch uploader.
=============================================================================
"""

import asyncio
import logging
import os
import signal
import sys
import time
import json
import aiosqlite
import dotenv

# Load environment from root folder
dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple

import aiohttp
from asyncua import Client

try:
    from asyncua.common.subscription import SubHandler as _BaseHandler
except ImportError:
    _BaseHandler = object

# ── Configuration ──────────────────────────────────────────────────────────
OPCUA_ENDPOINT = os.getenv("OPC_URL", "opc.tcp://localhost:4840/piccadily/")
FASTAPI_ENDPOINT = os.getenv("VITE_API_URL", "http://localhost")  # Through Nginx port 80
OPC_NS_URI = os.getenv("OPC_NS_URI", "urn:piccadily:boilerbridge")
TENANT_ID = os.getenv("TENANT_ID", "default_tenant")
PLANT_ID = os.getenv("PLANT_ID", "PICCADILY_PLANT_01")
DEVICE_ID = os.getenv("DEVICE_ID", "BOILER_PLC_01")
OPC_USERNAME = os.getenv("OPC_USER", "")
OPC_PASSWORD = os.getenv("OPC_PASS", "")

API_KEY = os.getenv("EDGE_API_KEY_RAW", "changeme")

MAX_BATCH = int(os.getenv("MAX_BATCH", "200"))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "2.0"))
PUB_INTERVAL_MS = int(os.getenv("PUB_INTERVAL_MS", "500"))
BASE_RETRY = float(os.getenv("BASE_RETRY", "2.0"))
MAX_RETRY = float(os.getenv("MAX_RETRY", "60.0"))
DEDUP_WINDOW_S = float(os.getenv("DEDUP_WINDOW_S", "0.5"))

# SQLite storage
_default_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edge_store.db")
STORE_DB = os.getenv("STORE_DB", _default_db)

# ── Logging ─────────────────────────────────────────────────────────────────
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("EdgeAgent")
logging.getLogger("asyncua").setLevel(logging.WARNING)

# API URL maps to the FastAPI ingestion route via Nginx
API_URL = f"{FASTAPI_ENDPOINT.rstrip('/')}/api/v1/telemetry/ingest"


@dataclass
class TelemetryPoint:
    tag_name: str
    value: float
    quality: str
    timestamp: str
    unit: Optional[str]
    source_id: str
    seq: int  # Internal sequence tracking

    def to_api_dict(self) -> dict:
        return {
            "tag_name": self.tag_name,
            "value": self.value,
            "quality": self.quality.upper(),
            "timestamp": self.timestamp,
            "unit": self.unit,
            "source_id": self.source_id,
        }


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


async def init_db(path: str):
    """Initialize the SQLite database with WAL mode for concurrency."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL
            )
            """
        )
        await db.commit()


class UniversalSubHandler(_BaseHandler):
    def __init__(
        self, db_conn: aiosqlite.Connection, dedup: DedupWindow, node_meta: Dict[str, tuple], seq_counter: list
    ):
        self._db = db_conn
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
            quality = "GOOD" if status.is_good() else "UNCERTAIN" if status.is_uncertain() else "BAD"

            # Skip bad quality readings in telemetry loop
            if quality == "BAD":
                self._stats_bad += 1
                return

            ts_srv = dv.SourceTimestamp or dv.ServerTimestamp or datetime.now(timezone.utc)
            ts_srv_iso = ts_srv.isoformat() if hasattr(ts_srv, "isoformat") else str(ts_srv)
            ts_epoch = ts_srv.timestamp() if hasattr(ts_srv, "timestamp") else time.time()

            dedup_key = f"{group}.{tag}"
            if self._dedup.is_duplicate(dedup_key, val, ts_epoch):
                self._stats_dup += 1
                return

            # Keep values numeric
            try:
                numeric_val = float(val)
            except (ValueError, TypeError):
                # If boolean, coerce to 1.0/0.0
                if isinstance(val, bool):
                    numeric_val = 1.0 if val else 0.0
                else:
                    return

            self._seq[0] += 1
            self._stats_good += 1

            # Database tag metadata contains seed tag names like 'TT-201', 'TE_FURN' etc.
            # We map tag browse name directly
            point = TelemetryPoint(
                tag_name=tag,
                value=numeric_val,
                quality=quality,
                timestamp=ts_srv_iso,
                unit=unit if unit != "-" else None,
                source_id=node_str,
                seq=self._seq[0],
            )

            # SQLite writes must be scheduled as background tasks to avoid blocking OPC thread
            # Actually asyncua allows calling async functions from datachange using create_task
            payload_str = json.dumps(point.to_api_dict())
            asyncio.create_task(self._async_insert(payload_str))

        except Exception as exc:
            log.error("SubHandler error: %s", exc, exc_info=True)

    async def _async_insert(self, payload: str):
        try:
            await self._db.execute("INSERT INTO telemetry_queue (payload) VALUES (?)", (payload,))
            await self._db.commit()
        except Exception as exc:
            log.error("Queue insert error: %s", exc)

    def status_change_notification(self, status):
        log.warning("OPC subscription status changed: %s", status)

    def get_stats(self) -> Tuple[int, int, int]:
        return self._stats_good, self._stats_bad, self._stats_dup


async def discover_tags(client: Client, ns_idx: int) -> List[Tuple[Any, str, str, str]]:
    """
    Browse objects folder hierarchy to find plant and device folders.
    Returns (tag_node, group_name, tag_name, unit).
    """
    discovered = []
    try:
        root = client.nodes.objects
        plant_node = await root.get_child(f"{ns_idx}:{PLANT_ID}")
        device_node = await plant_node.get_child(f"{ns_idx}:{DEVICE_ID}")

        group_children = await device_node.get_children()
        for group_node in group_children:
            group_name = (await group_node.read_browse_name()).Name
            if group_name.startswith("_"):
                continue

            tag_children = await group_node.get_children()
            for tag_node in tag_children:
                tag_name = (await tag_node.read_browse_name()).Name

                unit = "-"
                try:
                    desc = await tag_node.read_description()
                    if desc and desc.Text:
                        text = desc.Text
                        if "[" in text and text.endswith("]"):
                            unit = text[text.rfind("[") + 1 : -1]
                except Exception:
                    pass

                discovered.append((tag_node, group_name, tag_name, unit))
    except Exception as exc:
        log.error("Tag discovery failed: %s", exc)
    return discovered


async def uploader_task(
    db_path: str,
    stop_event: asyncio.Event,
):
    retry_delay = BASE_RETRY

    async with aiohttp.ClientSession(
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as session:
        async with aiosqlite.connect(db_path) as db:
            while not stop_event.is_set():
                try:
                    async with db.execute(
                        "SELECT id, payload FROM telemetry_queue ORDER BY id ASC LIMIT ?", (MAX_BATCH,)
                    ) as cursor:
                        rows = await cursor.fetchall()

                    if not rows:
                        await asyncio.sleep(FLUSH_INTERVAL)
                        continue

                    batch_payloads = [json.loads(row[1]) for row in rows]
                    last_id = rows[-1][0]

                    payload = {
                        "tenant_id": TENANT_ID,
                        "plant_id": PLANT_ID,
                        "points": batch_payloads,
                    }

                    try:
                        async with session.post(API_URL, json=payload) as resp:
                            if resp.status in (200, 201, 202):
                                await db.execute("DELETE FROM telemetry_queue WHERE id <= ?", (last_id,))
                                await db.commit()
                                log.info("Uploaded %d points (up to queue_id=%d)", len(batch_payloads), last_id)
                                retry_delay = BASE_RETRY
                            else:
                                body = await resp.text()
                                log.error("API error %d: %s", resp.status, body[:200])
                                await asyncio.sleep(retry_delay)
                                retry_delay = min(retry_delay * 2, MAX_RETRY)
                    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                        log.warning("Upload failed (%s) — retry in %.1fs", exc, retry_delay)
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, MAX_RETRY)

                except Exception as exc:
                    log.error("Uploader queue error: %s", exc)
                    await asyncio.sleep(retry_delay)


async def opc_client_task(
    db_path: str,
    stop_event: asyncio.Event,
):
    dedup = DedupWindow(DEDUP_WINDOW_S)
    seq_ctr = [0]
    retry_delay = BASE_RETRY

    while not stop_event.is_set():
        client = Client(url=OPCUA_ENDPOINT, timeout=10)
        if OPC_USERNAME:
            client.set_user(OPC_USERNAME)
            client.set_password(OPC_PASSWORD)

        try:
            async with client:
                log.info("OPC UA connected to %s", OPCUA_ENDPOINT)
                retry_delay = BASE_RETRY

                ns_idx = await client.get_namespace_index(OPC_NS_URI)
                log.info("Namespace index: %d  (URI: %s)", ns_idx, OPC_NS_URI)

                tags = await discover_tags(client, ns_idx)
                log.info("Discovered %d tags across OPC UA namespace", len(tags))

                if not tags:
                    log.error("No tags discovered — check PLANT_ID/DEVICE_ID")
                    await asyncio.sleep(retry_delay)
                    continue

                node_meta: Dict[str, tuple] = {}
                nodes_to_subscribe = []

                for node, group, tag, unit in tags:
                    node_meta[str(node)] = (group, tag, unit)
                    nodes_to_subscribe.append(node)

                groups: Dict[str, int] = {}
                for _, g, _, _ in tags:
                    groups[g] = groups.get(g, 0) + 1
                for g, c in sorted(groups.items()):
                    log.info("  Group %-20s : %3d tags", g, c)

                async with aiosqlite.connect(db_path) as db:
                    handler = UniversalSubHandler(db, dedup, node_meta, seq_ctr)
                    sub = await client.create_subscription(PUB_INTERVAL_MS, handler)

                    # Subscribe in chunks of 50 to avoid network timeouts
                    CHUNK = 50
                    for i in range(0, len(nodes_to_subscribe), CHUNK):
                        chunk = nodes_to_subscribe[i : i + CHUNK]
                        await sub.subscribe_data_change(chunk)

                    log.info("=" * 60)
                    log.info("  ALL %d SUBSCRIPTIONS ACTIVE", len(nodes_to_subscribe))
                    log.info("=" * 60)

                    while not stop_event.is_set():
                        await asyncio.sleep(30.0)
                        good, bad, dup = handler.get_stats()
                        log.info(
                            "STATS | Good=%d | Bad=%d | Dedup=%d | Seq=%d",
                            good,
                            bad,
                            dup,
                            seq_ctr[0],
                        )

                    await sub.delete()

        except Exception as exc:
            log.error("OPC connection error: %s — retry in %.1fs", exc, retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, MAX_RETRY)


async def main():
    log.info("=" * 60)
    log.info("  Universal OPC UA Edge Agent v3.0")
    log.info("  Tenant ID   : %s", TENANT_ID)
    log.info("  Plant ID    : %s", PLANT_ID)
    log.info("  Device ID   : %s", DEVICE_ID)
    log.info("  OPC UA      : %s", OPCUA_ENDPOINT)
    log.info("  Namespace   : %s", OPC_NS_URI)
    log.info("  Cloud API   : %s", API_URL)
    log.info("  Batch/Flush : %d / %.1fs", MAX_BATCH, FLUSH_INTERVAL)
    log.info("  Store DB    : %s", STORE_DB)
    log.info("=" * 60)

    await init_db(STORE_DB)
    stop_event = asyncio.Event()

    def _shutdown():
        log.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass  # Windows fallback

    await asyncio.gather(
        opc_client_task(STORE_DB, stop_event),
        uploader_task(STORE_DB, stop_event),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Edge agent stopped by user.")
