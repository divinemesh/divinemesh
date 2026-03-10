"""
DivineMesh Coordinator Server
"For where two or three gather in my name, there am I with them." — Matthew 18:20

Central coordinator that manages node registration, heartbeats,
task distribution, and proof verification.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
)
log = logging.getLogger("divinemesh.coordinator")

# ── In-memory store (replace with Redis/PostgreSQL for production) ────────────

nodes: Dict[str, dict] = {}          # node_id -> node info
proofs: List[dict] = []              # submitted compute proofs
tasks: List[dict] = []               # pending tasks
stats = {
    "total_nodes_ever": 0,
    "total_proofs": 0,
    "total_compute_seconds": 0,
    "started_at": datetime.utcnow().isoformat(),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def now_ts() -> float:
    return time.time()

def active_nodes() -> List[dict]:
    cutoff = now_ts() - 90  # 90s heartbeat timeout
    return [n for n in nodes.values() if n["last_seen"] > cutoff]

def node_summary(n: dict) -> dict:
    return {
        "node_id":        n["node_id"],
        "wallet_address": n["wallet_address"],
        "tier":           n["tier"],
        "score":          n["score"],
        "cpu_cores":      n["hw"].get("cpu_cores", 0),
        "ram_gb":         n["hw"].get("ram_gb", 0),
        "has_gpu":        n["hw"].get("has_gpu", False),
        "online":         (now_ts() - n["last_seen"]) < 90,
        "joined_at":      n["joined_at"],
        "last_seen":      n["last_seen"],
        "earnings_dmc":   n.get("earnings_dmc", 0.0),
    }


# ── Middleware ────────────────────────────────────────────────────────────────

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        })
    resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@web.middleware
async def log_middleware(request, handler):
    start = time.time()
    try:
        resp = await handler(request)
        ms = int((time.time() - start) * 1000)
        log.info(f"{request.method} {request.path} → {resp.status} ({ms}ms)")
        return resp
    except web.HTTPException as e:
        log.warning(f"{request.method} {request.path} → {e.status}")
        raise


# ── Routes ────────────────────────────────────────────────────────────────────

routes = web.RouteTableDef()


@routes.get("/")
async def root(req):
    return web.json_response({
        "service":  "DivineMesh Coordinator",
        "version":  "1.0.0",
        "verse":    "Matthew 18:20",
        "nodes_online": len(active_nodes()),
        "uptime_seconds": int(time.time() - time.mktime(
            datetime.fromisoformat(stats["started_at"]).timetuple())),
        "status":   "operational",
    })


@routes.get("/health")
async def health(req):
    return web.json_response({"status": "ok", "ts": now_ts()})


# ── Node Registration ─────────────────────────────────────────────────────────

@routes.post("/api/v1/register")
async def register_node(req):
    try:
        data = await req.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    node_id = data.get("node_id", "").strip()
    wallet  = data.get("wallet_address", "").strip()
    hw      = data.get("hardware", {})
    tier    = data.get("tier", "free")

    if not node_id or not node_id.startswith("DM-"):
        raise web.HTTPBadRequest(reason="Invalid node_id")
    if not wallet or not wallet.startswith("0x"):
        raise web.HTTPBadRequest(reason="Invalid wallet_address")

    is_new = node_id not in nodes
    nodes[node_id] = {
        "node_id":        node_id,
        "wallet_address": wallet,
        "hw":             hw,
        "tier":           tier,
        "score":          hw.get("compute_score", 1.0),
        "joined_at":      nodes.get(node_id, {}).get("joined_at", now_ts()),
        "last_seen":      now_ts(),
        "earnings_dmc":   nodes.get(node_id, {}).get("earnings_dmc", 0.0),
        "ip_hash":        hashlib.sha256(
            req.remote.encode()).hexdigest()[:16] if req.remote else "unknown",
    }

    if is_new:
        stats["total_nodes_ever"] += 1
        log.info(f"New node registered: {node_id} wallet={wallet[:10]}...")
    else:
        log.info(f"Node re-registered: {node_id}")

    return web.json_response({
        "status":       "registered",
        "node_id":      node_id,
        "network":      "polygon",
        "coordinator":  "coordinator.divinemesh.com",
        "heartbeat_interval": 30,
        "task_poll_interval": 5,
        "message":      "Welcome to DivineMesh. Give, and it will be given to you. — Luke 6:38",
    })


# ── Heartbeat ─────────────────────────────────────────────────────────────────

@routes.post("/api/v1/heartbeat")
async def heartbeat(req):
    try:
        data = await req.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    node_id = data.get("node_id", "").strip()
    if not node_id or node_id not in nodes:
        raise web.HTTPUnauthorized(reason="Unknown node — please register first")

    nodes[node_id]["last_seen"] = now_ts()
    nodes[node_id]["hw"] = data.get("hardware", nodes[node_id]["hw"])

    # Find a pending task for this node
    pending = [t for t in tasks if t["status"] == "pending"]
    assigned_task = None
    if pending:
        assigned_task = pending[0]
        assigned_task["status"] = "assigned"
        assigned_task["assigned_to"] = node_id
        assigned_task["assigned_at"] = now_ts()

    return web.json_response({
        "status":        "ok",
        "ts":            now_ts(),
        "nodes_online":  len(active_nodes()),
        "task":          assigned_task,
        "message":       "Keep working — your reward is being recorded.",
    })


# ── Proof Submission ──────────────────────────────────────────────────────────

@routes.post("/api/v1/proof")
async def submit_proof(req):
    try:
        data = await req.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    node_id = data.get("node_id", "").strip()
    if not node_id or node_id not in nodes:
        raise web.HTTPUnauthorized(reason="Unknown node")

    proof = {
        "proof_id":    str(uuid.uuid4()),
        "node_id":     node_id,
        "task_type":   data.get("task_type", "generic"),
        "cpu_seconds": float(data.get("cpu_seconds", 0)),
        "gpu_seconds": float(data.get("gpu_seconds", 0)),
        "ram_gb_hours":float(data.get("ram_gb_hours", 0)),
        "merkle_root": data.get("merkle_root", ""),
        "submitted_at":now_ts(),
        "status":      "verified",  # In production: verify merkle proof
    }

    # Calculate DMC reward: CPU_sec + 4*GPU_sec + 0.5*RAM_GB*hr
    dmc_reward = (
        proof["cpu_seconds"] * 0.001 +
        proof["gpu_seconds"] * 0.004 +
        proof["ram_gb_hours"] * 0.0005
    )
    proof["dmc_reward"] = round(dmc_reward, 6)

    proofs.append(proof)
    nodes[node_id]["earnings_dmc"] = round(
        nodes[node_id].get("earnings_dmc", 0) + dmc_reward, 6)

    stats["total_proofs"] += 1
    stats["total_compute_seconds"] += proof["cpu_seconds"] + proof["gpu_seconds"]

    log.info(f"Proof from {node_id}: +{dmc_reward:.4f} DMC")

    return web.json_response({
        "status":     "verified",
        "proof_id":   proof["proof_id"],
        "dmc_reward": dmc_reward,
        "message":    "Well done, good and faithful servant. — Matthew 25:21",
    })


# ── Stats & Network Info ──────────────────────────────────────────────────────

@routes.get("/api/v1/stats")
async def get_stats(req):
    online = active_nodes()
    total_score = sum(n["score"] for n in online)
    return web.json_response({
        "nodes_online":          len(online),
        "nodes_total_ever":      stats["total_nodes_ever"],
        "total_proofs":          stats["total_proofs"],
        "total_compute_seconds": stats["total_compute_seconds"],
        "total_score":           round(total_score, 2),
        "tasks_pending":         len([t for t in tasks if t["status"] == "pending"]),
        "dmc_distributed":       round(sum(p["dmc_reward"] for p in proofs), 4),
        "coordinator_uptime":    stats["started_at"],
        "network":               "polygon",
        "verse":                 "Give, and it will be given to you. — Luke 6:38",
    })


@routes.get("/api/v1/nodes")
async def get_nodes(req):
    limit = min(int(req.rel_url.query.get("limit", 50)), 200)
    online_only = req.rel_url.query.get("online", "false").lower() == "true"
    node_list = active_nodes() if online_only else list(nodes.values())
    node_list.sort(key=lambda n: n["last_seen"], reverse=True)
    return web.json_response({
        "nodes": [node_summary(n) for n in node_list[:limit]],
        "total": len(node_list),
    })


@routes.get("/api/v1/nodes/{node_id}")
async def get_node(req):
    node_id = req.match_info["node_id"]
    if node_id not in nodes:
        raise web.HTTPNotFound(reason="Node not found")
    return web.json_response(node_summary(nodes[node_id]))


@routes.get("/api/v1/leaderboard")
async def leaderboard(req):
    sorted_nodes = sorted(
        nodes.values(),
        key=lambda n: n.get("earnings_dmc", 0),
        reverse=True
    )[:20]
    return web.json_response({
        "leaderboard": [
            {
                "rank":         i + 1,
                "node_id":      n["node_id"],
                "wallet":       n["wallet_address"][:10] + "...",
                "earnings_dmc": n.get("earnings_dmc", 0),
                "score":        n["score"],
                "online":       (now_ts() - n["last_seen"]) < 90,
            }
            for i, n in enumerate(sorted_nodes)
        ]
    })


# ── Task Management (for project owners) ──────────────────────────────────────

@routes.post("/api/v1/tasks")
async def submit_task(req):
    try:
        data = await req.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON")

    task = {
        "task_id":      str(uuid.uuid4()),
        "task_type":    data.get("task_type", "generic"),
        "payload":      data.get("payload", {}),
        "owner_wallet": data.get("owner_wallet", ""),
        "dmc_budget":   float(data.get("dmc_budget", 0)),
        "status":       "pending",
        "created_at":   now_ts(),
        "assigned_to":  None,
    }
    tasks.append(task)
    log.info(f"New task: {task['task_id']} type={task['task_type']}")
    return web.json_response({
        "status":  "queued",
        "task_id": task["task_id"],
        "message": "Your task has been submitted to the network.",
    })


# ── Background Tasks ──────────────────────────────────────────────────────────

async def cleanup_stale_tasks():
    """Re-queue tasks that were assigned but never completed."""
    while True:
        await asyncio.sleep(60)
        cutoff = now_ts() - 300  # 5 minutes
        for task in tasks:
            if task["status"] == "assigned" and task.get("assigned_at", 0) < cutoff:
                task["status"] = "pending"
                task["assigned_to"] = None
                log.info(f"Re-queued stale task: {task['task_id']}")


async def log_stats():
    """Log network stats every 5 minutes."""
    while True:
        await asyncio.sleep(300)
        online = len(active_nodes())
        log.info(
            f"Network stats: {online} nodes online | "
            f"{stats['total_proofs']} proofs | "
            f"{stats['total_compute_seconds']:.0f}s compute"
        )


# ── App Factory ───────────────────────────────────────────────────────────────

async def on_startup(app):
    asyncio.create_task(cleanup_stale_tasks())
    asyncio.create_task(log_stats())
    log.info("=" * 60)
    log.info("  DivineMesh Coordinator v1.0.0")
    log.info('  "For where two or three gather in my name,')
    log.info('   there am I with them." — Matthew 18:20')
    log.info("=" * 60)
    log.info(f"  Listening on port {os.getenv('PORT', '8888')}")


def create_app():
    app = web.Application(middlewares=[cors_middleware, log_middleware])
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8888))
    web.run_app(create_app(), host="0.0.0.0", port=port)
