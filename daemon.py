"""
DivineMesh Network Daemon
"Let your light shine before others, that they may see your good deeds." - Matthew 5:16

This daemon:
  1. Registers the node with the coordinator
  2. Polls for compute tasks
  3. Executes tasks in isolated sandbox (no data stored on disk)
  4. Submits proofs on-chain to earn DMC
  5. Exposes local REST API for the dashboard
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict, Any

import aiohttp
from aiohttp import web
import websockets

from .auth import IdentityManager, IPGuard
from .hardware_monitor import ComputeEngine, ResourceLimits, ComputeMode, HardwareProfile
from .blockchain import BlockchainClient, ComputeProof, MerkleTree, DMCWallet
from .encryption import SacredEncryptor, generate_sacred_id

log = logging.getLogger("divinemesh.daemon")

# ── Configuration ─────────────────────────────────────────────────────────────
COORDINATOR_URL = os.getenv("DIVINEMESH_COORDINATOR", "https://coordinator.divinemesh.io")
LOCAL_API_PORT = int(os.getenv("DIVINEMESH_PORT", "7474"))
HEARTBEAT_INTERVAL = 30   # seconds
TASK_POLL_INTERVAL = 5    # seconds
VERSION = "1.0.0"


class DivineMeshDaemon:
    """
    The core DivineMesh node process.
    'The Spirit of God has made me; the breath of the Almighty gives me life.' - Job 33:4
    """

    def __init__(
        self,
        identity_manager: IdentityManager,
        limits: ResourceLimits,
        network: str = "polygon",
        dmc_contract: str = None,
        registry_contract: str = None,
    ):
        self.idm = identity_manager
        self.limits = limits
        self.engine = ComputeEngine(limits)
        self.bc = BlockchainClient(network, dmc_contract, registry_contract)
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._pending_proofs: list = []
        self._lock = asyncio.Lock()
        self._stats_cache: Dict = {}

    # ── Startup ───────────────────────────────────────────────────────────────

    async def start(self):
        identity = self.idm.identity
        if not identity:
            raise RuntimeError("No identity loaded. Please register or login first.")

        self._running = True
        self.engine.start()
        self._session = aiohttp.ClientSession(
            headers={
                "X-DivineMesh-Node": identity.node_id,
                "X-DivineMesh-Version": VERSION,
            }
        )
        log.info(f"DivineMesh Daemon v{VERSION} starting | node={identity.node_id}")

        # Register with coordinator
        await self._register_node()

        # Start local REST API for dashboard
        app_task = asyncio.create_task(self._start_local_api())
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        task_loop_task = asyncio.create_task(self._task_poll_loop())
        proof_task = asyncio.create_task(self._proof_submit_loop())

        await asyncio.gather(app_task, heartbeat_task, task_loop_task, proof_task)

    async def stop(self):
        self._running = False
        self.engine.stop()
        if self._session:
            await self._session.close()
        log.info("DivineMesh Daemon stopped. 'Well done, good and faithful servant.' - Matthew 25:21")

    # ── Node Registration ─────────────────────────────────────────────────────

    async def _register_node(self):
        identity = self.idm.identity
        hw = HardwareProfile.detect()
        payload = {
            "node_id": identity.node_id,
            "public_key_pem": identity.public_key_pem,
            "ip_hash": identity.ip_hash,
            "mac_hash": identity.mac_hash,
            "wallet_address": identity.wallet_address,
            "hw_profile": hw.to_dict(),
            "hw_score": hw.compute_score(),
            "tier": identity.tier,
            "version": VERSION,
        }
        try:
            async with self._session.post(
                f"{COORDINATOR_URL}/api/v1/nodes/register", json=payload, timeout=10
            ) as resp:
                if resp.status == 200:
                    log.info("Node registered with coordinator ✓")
                elif resp.status == 409:
                    log.info("Node already registered — updating heartbeat")
                else:
                    log.warning(f"Registration returned {resp.status}")
        except Exception as e:
            log.error(f"Registration failed (will retry): {e}")

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        while self._running:
            try:
                stats = self.engine.get_stats()
                identity = self.idm.identity
                payload = {
                    "node_id": identity.node_id,
                    "ts": int(time.time()),
                    "stats": stats,
                    "can_accept": stats["can_accept"],
                }
                async with self._session.post(
                    f"{COORDINATOR_URL}/api/v1/nodes/heartbeat", json=payload, timeout=5
                ) as resp:
                    if resp.status != 200:
                        log.debug(f"Heartbeat non-200: {resp.status}")
                async with self._lock:
                    self._stats_cache = stats
            except Exception as e:
                log.debug(f"Heartbeat error: {e}")
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    # ── Task Polling ──────────────────────────────────────────────────────────

    async def _task_poll_loop(self):
        """
        Poll coordinator for available tasks.
        'Whatever you do, do it all for the glory of God.' - 1 Corinthians 10:31
        """
        while self._running:
            try:
                if self.engine.can_accept_task()[0]:
                    identity = self.idm.identity
                    async with self._session.get(
                        f"{COORDINATOR_URL}/api/v1/tasks/next",
                        params={"node_id": identity.node_id},
                        timeout=5,
                    ) as resp:
                        if resp.status == 200:
                            task_data = await resp.json()
                            if task_data.get("task_id"):
                                asyncio.create_task(self._execute_task(task_data))
            except Exception as e:
                log.debug(f"Task poll error: {e}")
            await asyncio.sleep(TASK_POLL_INTERVAL)

    async def _execute_task(self, task_data: Dict):
        """
        Execute a single compute task and generate proof.
        SECURITY: No task data is ever written to disk. RAM only.
        """
        task_id = task_data["task_id"]
        log.info(f"Executing task {task_id} type={task_data.get('type')}")
        start_ts = int(time.time())

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            self.engine.submit_task,
            task_id,
            task_data.get("type", "generic"),
            task_data.get("payload", {}),
        )

        end_ts = int(time.time())
        if result is None:
            return

        # Build compute proof
        result_hash = hashlib.sha3_256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        proof = ComputeProof(
            task_id=task_id,
            node_id=self.idm.identity.node_id,
            cpu_seconds=result.get("wall_seconds", 0),
            gpu_seconds=0.0,
            ram_gb_hours=0.0,
            start_ts=start_ts,
            end_ts=end_ts,
            result_hash=result_hash,
        )

        # Submit result to coordinator
        try:
            async with self._session.post(
                f"{COORDINATOR_URL}/api/v1/tasks/{task_id}/result",
                json={"proof": proof.__dict__, "result": result},
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    log.info(f"Task {task_id} completed | units={proof.compute_units():.2f}")
                    async with self._lock:
                        self._pending_proofs.append(proof)
        except Exception as e:
            log.error(f"Result submit error for {task_id}: {e}")

    # ── On-Chain Proof Submission ─────────────────────────────────────────────

    async def _proof_submit_loop(self):
        """
        Batch pending proofs into a Merkle tree and anchor on-chain every 10 min.
        'Bring the whole tithe into the storehouse.' - Malachi 3:10
        """
        while self._running:
            await asyncio.sleep(600)  # 10-minute batching window
            async with self._lock:
                if not self._pending_proofs:
                    continue
                batch = list(self._pending_proofs)
                self._pending_proofs.clear()

            leaves = [p.to_hash().encode() for p in batch]
            tree = MerkleTree(leaves)
            log.info(f"Anchoring {len(batch)} proofs | merkle_root={tree.root[:16]}...")
            # In production: call self.bc.claim_reward(wallet, proof)

    # ── Local REST API ────────────────────────────────────────────────────────

    async def _start_local_api(self):
        """
        Local API consumed by the web dashboard.
        Bound to localhost only — never exposed externally.
        """
        app = web.Application()
        app.router.add_get("/api/status", self._api_status)
        app.router.add_get("/api/stats", self._api_stats)
        app.router.add_get("/api/balance", self._api_balance)
        app.router.add_get("/api/identity", self._api_identity)
        app.router.add_post("/api/limits", self._api_set_limits)
        app.router.add_get("/api/health", lambda r: web.json_response({"status": "alive", "verse": "John 3:16"}))

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", LOCAL_API_PORT)
        await site.start()
        log.info(f"Local API listening on http://127.0.0.1:{LOCAL_API_PORT}")
        while self._running:
            await asyncio.sleep(1)

    async def _api_status(self, request):
        identity = self.idm.identity
        return web.json_response({
            "running": self._running,
            "node_id": identity.node_id if identity else None,
            "version": VERSION,
            "tier": identity.tier if identity else "none",
        })

    async def _api_stats(self, request):
        async with self._lock:
            return web.json_response(self._stats_cache)

    async def _api_balance(self, request):
        identity = self.idm.identity
        if not identity:
            return web.json_response({"error": "not_authenticated"}, status=401)
        balance = self.bc.get_dmc_balance(identity.wallet_address)
        return web.json_response({
            "address": identity.wallet_address,
            "dmc_balance": str(balance),
            "tier": identity.tier,
        })

    async def _api_identity(self, request):
        identity = self.idm.identity
        if not identity:
            return web.json_response({"error": "not_authenticated"}, status=401)
        return web.json_response({
            "node_id": identity.node_id,
            "wallet_address": identity.wallet_address,
            "tier": identity.tier,
            "totp_enabled": identity.totp_enabled,
            "created_ts": identity.created_ts,
        })

    async def _api_set_limits(self, request):
        try:
            data = await request.json()
            self.limits.max_cpu_pct = float(data.get("max_cpu_pct", self.limits.max_cpu_pct))
            self.limits.max_ram_pct = float(data.get("max_ram_pct", self.limits.max_ram_pct))
            self.limits.max_gpu_pct = float(data.get("max_gpu_pct", self.limits.max_gpu_pct))
            self.limits.idle_only = bool(data.get("idle_only", self.limits.idle_only))
            return web.json_response({"ok": True})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="DivineMesh Node Daemon")
    parser.add_argument("command", choices=["register", "start", "status", "balance", "2fa"])
    parser.add_argument("--password", help="Node password")
    parser.add_argument("--network", default="polygon")
    args = parser.parse_args()

    idm = IdentityManager()
    limits = ResourceLimits()

    if args.command == "register":
        print("╔════════════════════════════════════════════════╗")
        print('║  "I am the way and the truth" - John 14:6     ║')
        print("║          DivineMesh Node Registration          ║")
        print("╚════════════════════════════════════════════════╝\n")
        identity, password = idm.create_new_identity()
        print(f"✓ Node ID       : {identity.node_id}")
        print(f"✓ Wallet Address: {identity.wallet_address}")
        print(f"\n⚠  AUTO-GENERATED PASSWORD (save this — shown ONCE):")
        print(f"   {password}\n")
        print("Your identity has been saved. No personal info collected.")
        return

    if args.command == "2fa":
        password = args.password or input("Password: ")
        secret, uri = idm.enable_2fa(password)
        print(f"2FA Secret : {secret}")
        print(f"QR URI     : {uri}")
        print("Scan this with your authenticator app.")
        return

    if args.command == "status":
        import requests
        try:
            r = requests.get(f"http://127.0.0.1:{LOCAL_API_PORT}/api/status", timeout=2)
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print("Daemon not running.")
        return

    if args.command == "balance":
        import requests
        try:
            r = requests.get(f"http://127.0.0.1:{LOCAL_API_PORT}/api/balance", timeout=2)
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print("Daemon not running.")
        return

    if args.command == "start":
        password = args.password or input("Password: ")
        if not idm.authenticate(password):
            print("Authentication failed.")
            sys.exit(1)
        daemon = DivineMeshDaemon(idm, limits, network=args.network)
        print(f"Starting DivineMesh Daemon | node={idm.identity.node_id}")
        print('"Let your light shine before others." - Matthew 5:16\n')

        def _shutdown(signum, frame):
            asyncio.create_task(daemon.stop())
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        asyncio.run(daemon.start())


if __name__ == "__main__":
    main()
