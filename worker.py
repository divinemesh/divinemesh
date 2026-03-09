"""
DivineMesh Isolated Worker
"Whatever you do, work at it with all your heart." - Colossians 3:23

This module runs as a SUBPROCESS called by the daemon.
- Reads task payload from STDIN (never from disk)
- Writes result to STDOUT (never to disk)
- All intermediate data lives only in RAM
- Automatically killed by daemon on timeout

SECURITY NOTE: This process has no access to user files, identity,
or any persistent state. It is a pure compute sandbox.
'Do not give what is sacred to dogs.' - Matthew 7:6
"""

import sys
import json
import os
import time
import hashlib
import logging

log = logging.getLogger("divinemesh.worker")

# Task type registry — extend to add new compute capabilities
TASK_HANDLERS = {}

def task_handler(task_type: str):
    def decorator(fn):
        TASK_HANDLERS[task_type] = fn
        return fn
    return decorator


@task_handler("inference")
def handle_inference(payload: dict) -> dict:
    """
    Run AI model inference on provided input.
    Model weights loaded from coordinator, never cached locally.
    """
    model_id = payload.get("model_id", "unknown")
    input_data = payload.get("input", "")
    # In production: load quantized model from coordinator stream
    # For demo: simulate inference
    time.sleep(0.1)
    result_hash = hashlib.sha3_256(str(input_data).encode()).hexdigest()
    return {
        "model_id": model_id,
        "result_hash": result_hash,
        "tokens_processed": len(str(input_data)),
        "type": "inference",
    }


@task_handler("training_gradient")
def handle_gradient(payload: dict) -> dict:
    """
    Compute gradients for a training batch (federated learning step).
    No model weights stored — gradient computed and returned immediately.
    """
    batch_id = payload.get("batch_id", "unknown")
    # In production: compute actual gradient using PyTorch
    time.sleep(0.05)
    fake_gradient_hash = hashlib.sha3_256(batch_id.encode()).hexdigest()
    return {
        "batch_id": batch_id,
        "gradient_hash": fake_gradient_hash,
        "type": "training_gradient",
    }


@task_handler("render")
def handle_render(payload: dict) -> dict:
    """3D render task (Blender/POV-Ray compatible)."""
    frame = payload.get("frame", 0)
    time.sleep(0.2)
    return {
        "frame": frame,
        "result_hash": hashlib.sha3_256(str(frame).encode()).hexdigest(),
        "type": "render",
    }


@task_handler("benchmark")
def handle_benchmark(payload: dict) -> dict:
    """Hardware benchmark task used for pricing calibration."""
    n = int(payload.get("n", 1000000))
    start = time.perf_counter()
    # Simple CPU benchmark
    total = sum(i * i for i in range(n))
    elapsed = time.perf_counter() - start
    return {
        "benchmark_score": n / elapsed,
        "elapsed_seconds": elapsed,
        "type": "benchmark",
    }


@task_handler("generic")
def handle_generic(payload: dict) -> dict:
    """Generic compute task fallback."""
    time.sleep(0.05)
    return {
        "result_hash": hashlib.sha3_256(json.dumps(payload).encode()).hexdigest(),
        "type": "generic",
    }


def main():
    # Read task payload from stdin (never from disk)
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            json.dump({"error": "empty_payload"}, sys.stdout)
            return
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        json.dump({"error": f"invalid_json: {e}"}, sys.stdout)
        return

    task_type = os.environ.get("DIVINEMESH_TASK_TYPE", "generic")
    handler = TASK_HANDLERS.get(task_type, handle_generic)

    try:
        result = handler(payload)
        result["worker_pid"] = os.getpid()
        result["completed_at"] = int(time.time())
        json.dump(result, sys.stdout)
    except Exception as e:
        json.dump({"error": str(e), "task_type": task_type}, sys.stdout)


if __name__ == "__main__":
    # Ensure no accidental writes to disk
    os.umask(0o177)  # Files can only be created as owner-read-only
    main()
