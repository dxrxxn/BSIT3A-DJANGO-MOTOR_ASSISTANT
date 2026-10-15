"""
AI engine worker — launches triposr_runner.py in .venv_ai as a subprocess.
ROOT is resolved to the Django project root (BASE_DIR).
"""
from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncGenerator

log = logging.getLogger(__name__)

# Project root = 4 levels up from this file:
# apps/studio/ai_engine/worker.py → apps/studio/ai_engine → apps/studio → apps → ROOT
ROOT       = Path(__file__).resolve().parent.parent.parent.parent
_AI_PYTHON = ROOT / ".venv_ai" / "Scripts" / "python.exe"
_RUNNER    = ROOT / "apps" / "studio" / "ai_engine" / "triposr_runner.py"


def ai_venv_ready() -> tuple[bool, str]:
    if not _AI_PYTHON.exists():
        return False, (
            f".venv_ai not found at {_AI_PYTHON}. "
            "Run: python -m venv .venv_ai  then  .venv_ai\\Scripts\\pip install -r requirements_ai.txt"
        )
    if not _RUNNER.exists():
        return False, f"triposr_runner.py missing at {_RUNNER}."
    return True, "ok"


async def run_triposr(
    image_path: str | Path,
    output_dir: str | Path,
    device: str = "auto",
) -> AsyncGenerator[dict, None]:
    ready, reason = ai_venv_ready()
    if not ready:
        yield {"type": "error", "msg": reason}
        return

    cmd = [str(_AI_PYTHON), str(_RUNNER),
           "--image", str(image_path),
           "--output", str(output_dir),
           "--device", device]
    log.info("Launching AI subprocess: %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(ROOT),
    )
    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            yield {"type": "progress", "pct": -1, "msg": line}
    await proc.wait()
    if proc.returncode != 0:
        stderr = await proc.stderr.read() if proc.stderr else b""
        yield {"type": "error",
               "msg": f"AI process exited {proc.returncode}. " + stderr.decode("utf-8", errors="replace")[-500:]}
