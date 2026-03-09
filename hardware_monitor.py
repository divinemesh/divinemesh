"""
DivineMesh Hardware Monitor & Compute Engine
"Whatever your hand finds to do, do it with all your might." - Ecclesiastes 9:10
"""

import os
import sys
import time
import psutil
import logging
import platform
import threading
import subprocess
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Tuple
from enum import Enum

log = logging.getLogger("divinemesh.hardware")

# GPU support — gracefully degrade if unavailable
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

try:
    import pycuda.driver as cuda
    import pycuda.autoinit
    CUDA_AVAILABLE = True
except Exception:
    CUDA_AVAILABLE = False


class ComputeMode(Enum):
    CPU_ONLY = "cpu_only"
    CPU_GPU = "cpu_gpu"
    GPU_ONLY = "gpu_only"


@dataclass
class HardwareProfile:
    """
    Complete hardware fingerprint for pricing and capability advertisement.
    'For we are God's handiwork.' - Ephesians 2:10
    """
    cpu_brand: str = ""
    cpu_cores_physical: int = 0
    cpu_cores_logical: int = 0
    cpu_freq_max_mhz: float = 0.0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpus: List[Dict] = field(default_factory=list)
    platform: str = ""
    python_bits: int = 64

    @classmethod
    def detect(cls) -> "HardwareProfile":
        p = cls()
        p.platform = platform.system()
        p.python_bits = 64 if sys.maxsize > 2**32 else 32
        try:
            import cpuinfo
            info = cpuinfo.get_cpu_info()
            p.cpu_brand = info.get("brand_raw", "Unknown CPU")
        except Exception:
            p.cpu_brand = platform.processor() or "Unknown CPU"
        p.cpu_cores_physical = psutil.cpu_count(logical=False) or 1
        p.cpu_cores_logical = psutil.cpu_count(logical=True) or 1
        freq = psutil.cpu_freq()
        p.cpu_freq_max_mhz = freq.max if freq else 0.0
        mem = psutil.virtual_memory()
        p.ram_total_gb = mem.total / 1e9
        p.ram_available_gb = mem.available / 1e9
        if GPU_AVAILABLE:
            try:
                for g in GPUtil.getGPUs():
                    p.gpus.append({
                        "id": g.id,
                        "name": g.name,
                        "vram_mb": g.memoryTotal,
                        "driver": g.driver,
                    })
            except Exception:
                pass
        return p

    def compute_score(self) -> float:
        """Normalized compute score used for reward pricing."""
        cpu_score = self.cpu_cores_physical * (self.cpu_freq_max_mhz / 1000)
        ram_score = self.ram_total_gb * 0.5
        gpu_score = sum(g.get("vram_mb", 0) / 1000 * 4 for g in self.gpus)
        return round(cpu_score + ram_score + gpu_score, 2)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResourceLimits:
    """
    Configurable resource limits — subscribers choose how much to share.
    'Give, and it will be given to you.' - Luke 6:38
    """
    max_cpu_pct: float = 50.0        # % of total CPU to offer
    max_ram_pct: float = 30.0        # % of total RAM to offer
    max_gpu_pct: float = 70.0        # % of GPU VRAM to offer
    max_upload_mbps: float = 50.0
    max_download_mbps: float = 50.0
    allow_gpu: bool = True
    active_hours_start: int = 0      # Hour of day (UTC) when sharing starts
    active_hours_end: int = 24       # Hour of day (UTC) when sharing ends
    idle_only: bool = True           # Only share when system is idle

    @property
    def is_active_now(self) -> bool:
        hour = time.gmtime().tm_hour
        return self.active_hours_start <= hour < self.active_hours_end

    def within_limits(self, cpu_pct: float, ram_pct: float) -> bool:
        return cpu_pct <= self.max_cpu_pct and ram_pct <= self.max_ram_pct


class ResourceMonitor:
    """
    Real-time hardware utilization monitor with threshold enforcement.
    'The prudent see danger and take refuge.' - Proverbs 22:3
    """

    def __init__(self, limits: ResourceLimits):
        self.limits = limits
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current: Dict = {}
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("ResourceMonitor started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                net = psutil.net_io_counters()
                sample = {
                    "ts": time.time(),
                    "cpu_pct": cpu,
                    "ram_pct": mem.percent,
                    "ram_used_gb": mem.used / 1e9,
                    "ram_available_gb": mem.available / 1e9,
                    "net_bytes_sent": net.bytes_sent,
                    "net_bytes_recv": net.bytes_recv,
                }
                if GPU_AVAILABLE:
                    gpus = GPUtil.getGPUs()
                    sample["gpus"] = [
                        {"id": g.id, "load_pct": g.load * 100, "vram_used_mb": g.memoryUsed}
                        for g in gpus
                    ]
                with self._lock:
                    self._current = sample
            except Exception as e:
                log.warning(f"Monitor error: {e}")
            time.sleep(2)

    def snapshot(self) -> Dict:
        with self._lock:
            return dict(self._current)

    def is_idle(self) -> bool:
        s = self.snapshot()
        return s.get("cpu_pct", 100) < 20 and s.get("ram_pct", 100) < 60

    def available_cpu_pct(self) -> float:
        s = self.snapshot()
        own_cpu = s.get("cpu_pct", 100)
        return max(0, self.limits.max_cpu_pct - own_cpu)

    def available_ram_gb(self) -> float:
        s = self.snapshot()
        return min(s.get("ram_available_gb", 0), HardwareProfile.detect().ram_total_gb * self.limits.max_ram_pct / 100)


class SandboxedTask:
    """
    Runs a compute task inside a resource-constrained subprocess.
    CRITICAL: No user data touches disk — all compute is ephemeral in RAM.
    'Do not give what is sacred to dogs.' - Matthew 7:6
    """

    def __init__(self, task_id: str, task_type: str, payload: dict, limits: ResourceLimits):
        self.task_id = task_id
        self.task_type = task_type
        self.payload = payload
        self.limits = limits
        self._proc: Optional[subprocess.Popen] = None
        self.result = None
        self.start_time = 0.0
        self.end_time = 0.0

    def run(self, timeout: int = 3600) -> Dict:
        """Execute task in isolated subprocess with strict resource limits."""
        self.start_time = time.time()
        env = {
            "DIVINEMESH_TASK_ID": self.task_id,
            "DIVINEMESH_TASK_TYPE": self.task_type,
            "DIVINEMESH_MAX_CPU_PCT": str(self.limits.max_cpu_pct),
            "DIVINEMESH_MAX_RAM_PCT": str(self.limits.max_ram_pct),
            "PATH": os.environ.get("PATH", ""),
        }
        # Serialize payload to stdin — nothing written to disk
        payload_json = json.dumps(self.payload)

        try:
            self._proc = subprocess.Popen(
                [sys.executable, "-m", "divinemesh.worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )
            stdout, stderr = self._proc.communicate(input=payload_json, timeout=timeout)
            self.end_time = time.time()
            result_data = json.loads(stdout) if stdout.strip() else {}
            result_data["task_id"] = self.task_id
            result_data["wall_seconds"] = self.end_time - self.start_time
            if stderr:
                log.debug(f"Task {self.task_id} stderr: {stderr[:500]}")
            return result_data
        except subprocess.TimeoutExpired:
            if self._proc:
                self._proc.kill()
            self.end_time = time.time()
            return {"task_id": self.task_id, "error": "timeout", "wall_seconds": timeout}
        except Exception as e:
            self.end_time = time.time()
            log.error(f"Task {self.task_id} failed: {e}")
            return {"task_id": self.task_id, "error": str(e), "wall_seconds": 0}

    def kill(self):
        if self._proc and self._proc.poll() is None:
            self._proc.kill()


class ComputeEngine:
    """
    Manages task scheduling, hardware allocation, and proof generation.
    'Let each person examine their own work.' - Galatians 6:4
    """

    def __init__(self, limits: ResourceLimits, mode: ComputeMode = ComputeMode.CPU_GPU):
        self.limits = limits
        self.mode = mode
        self.monitor = ResourceMonitor(limits)
        self.profile = HardwareProfile.detect()
        self._active_tasks: Dict[str, SandboxedTask] = {}
        self._completed: List[Dict] = []
        self._lock = threading.Lock()

    def start(self):
        self.monitor.start()
        log.info(f"ComputeEngine started | score={self.profile.compute_score()} | mode={self.mode.value}")

    def stop(self):
        self.monitor.stop()
        with self._lock:
            for task in self._active_tasks.values():
                task.kill()

    def can_accept_task(self) -> Tuple[bool, str]:
        if not self.limits.is_active_now:
            return False, "outside_active_hours"
        if self.limits.idle_only and not self.monitor.is_idle():
            return False, "system_not_idle"
        if self.monitor.available_cpu_pct() < 5:
            return False, "insufficient_cpu"
        if self.monitor.available_ram_gb() < 0.5:
            return False, "insufficient_ram"
        return True, "ok"

    def submit_task(self, task_id: str, task_type: str, payload: dict) -> Optional[Dict]:
        ok, reason = self.can_accept_task()
        if not ok:
            log.info(f"Rejecting task {task_id}: {reason}")
            return None
        task = SandboxedTask(task_id, task_type, payload, self.limits)
        with self._lock:
            self._active_tasks[task_id] = task
        result = task.run()
        with self._lock:
            del self._active_tasks[task_id]
            self._completed.append(result)
        return result

    def get_stats(self) -> Dict:
        snap = self.monitor.snapshot()
        return {
            "profile": self.profile.to_dict(),
            "current": snap,
            "available_cpu_pct": self.monitor.available_cpu_pct(),
            "available_ram_gb": self.monitor.available_ram_gb(),
            "active_tasks": len(self._active_tasks),
            "completed_tasks": len(self._completed),
            "can_accept": self.can_accept_task()[0],
        }
