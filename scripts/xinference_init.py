"""Entrypoint wrapper: start xinference, wait for readiness, launch bge-m3 embedding model."""

import asyncio
import sys
import urllib.request
import urllib.error

XINFERENCE_READY_URL = "http://127.0.0.1:9997/v1/models"
LAUNCH_PAYLOAD = (
    b'{"model_name":"bge-m3","model_type":"embedding","model_engine":"transformers",'
    b'"model_uid":"bge-m3","gpu_utilization":1.0}'
)
MAX_WAIT = 120
LAUNCH_TIMEOUT = 60


async def wait_ready(timeout: float) -> bool:
    deadline = asyncio.monotonic() + timeout
    while asyncio.monotonic() < deadline:
        try:
            resp = urllib.request.urlopen(XINFERENCE_READY_URL, timeout=5)
            if resp.status == 200:
                return True
        except Exception:
            pass
        await asyncio.sleep(2)
    return False


async def launch_model(timeout: float) -> bool:
    deadline = asyncio.monotonic() + timeout
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:9997/v1/models",
            data=LAUNCH_PAYLOAD,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: urllib.request.urlopen(req, timeout=10)
        )
        body = resp.read()
        print(f"launch response: {resp.status} {body.decode()}", flush=True)
        return resp.status == 200
    except Exception as e:
        print(f"launch failed: {e}", flush=True)
        return False


async def main():
    print("Waiting for xinference to be ready...", flush=True)
    if not await wait_ready(MAX_WAIT):
        print("ERROR: xinference did not become ready in time", flush=True)
        sys.exit(1)
    print("Xinference is ready.", flush=True)

    ok = await launch_model(LAUNCH_TIMEOUT)
    if ok:
        print("bge-m3 model launched successfully.", flush=True)
    else:
        print("WARNING: bge-m3 launch returned non-200, continuing anyway.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
