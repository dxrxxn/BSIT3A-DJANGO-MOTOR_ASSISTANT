"""
PictureTo3D Studio — Django views.

Jobs run in background threads (no Celery required).
SSE streaming uses StreamingHttpResponse.
"""
from __future__ import annotations
import asyncio
import io
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import (
    JsonResponse, StreamingHttpResponse, FileResponse, HttpResponseNotFound
)
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.studio.ai_engine.worker   import run_triposr, ai_venv_ready
from apps.studio.mesh_processing.loader    import load_mesh
from apps.studio.mesh_processing.repair    import repair_mesh
from apps.studio.mesh_processing.validator import validate_mesh
from apps.studio.exporters.export          import export_mesh
from apps.studio.schemas                   import JobStatus, ValidationReport

log = logging.getLogger(__name__)

BASE_DIR     = Path(settings.BASE_DIR)
UPLOADS_DIR  = BASE_DIR / "media" / "studio" / "uploads"
OUTPUTS_DIR  = BASE_DIR / "media" / "studio" / "outputs"
HISTORY_FILE = OUTPUTS_DIR / "history.json"

# In-memory job store  {job_id: dict}
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(name: str) -> str:
    return ''.join(c if c.isalnum() or c in '._-' else '_' for c in name)


def _job_or_404(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def _progress(job: dict, pct: int, msg: str) -> None:
    with _jobs_lock:
        job["progress"] = pct
        job["log"].append(msg)


def _save_history() -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _jobs_lock:
        history = [
            {"job_id": j["job_id"], "status": j["status"],
             "filename": j.get("filename", ""), "created": j.get("created", 0)}
            for j in _jobs.values()
        ]
    HISTORY_FILE.write_text(json.dumps(history[-50:], indent=2))


def _scale_to_mm(mesh, unit, sx, sy, sz):
    if sx is None and sy is None and sz is None:
        longest = max(mesh.extents)
        return 100.0 / longest if longest > 0 else 1.0
    extents = mesh.extents
    targets = []
    if sx: targets.append(sx / extents[0])
    if sy: targets.append(sy / extents[1])
    if sz: targets.append(sz / extents[2])
    scale = sum(targets) / len(targets)
    return scale * {"mm": 1.0, "cm": 10.0, "in": 25.4}.get(unit, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Background job runner (thread)
# ─────────────────────────────────────────────────────────────────────────────

def _run_job_thread(job_id: str, params: dict) -> None:
    """Runs the full pipeline in a background thread."""
    with _jobs_lock:
        job = _jobs[job_id]

    def p(pct, msg):
        _progress(job, pct, msg)
        log.info("[%s] %d%% %s", job_id, pct, msg)

    image_path = UPLOADS_DIR / params["filename"]
    job_dir    = OUTPUTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. AI reconstruction ─────────────────────────────────────────────────
    with _jobs_lock:
        job["status"] = JobStatus.PROCESSING
    p(0, "Starting AI reconstruction…")

    raw_mesh_path = None

    async def _gather_triposr():
        nonlocal raw_mesh_path
        async for event in run_triposr(image_path, job_dir, params.get("device", "auto")):
            if event["type"] == "progress":
                pct = event.get("pct", -1)
                if pct >= 0:
                    with _jobs_lock:
                        job["progress"] = int(pct * 0.65)
                with _jobs_lock:
                    job["log"].append(event["msg"])
            elif event["type"] == "result":
                raw_mesh_path = event["mesh_path"]
            elif event["type"] == "error":
                with _jobs_lock:
                    job["status"] = JobStatus.FAILED
                    job["error"]  = event["msg"]

    asyncio.run(_gather_triposr())

    with _jobs_lock:
        if job.get("status") == JobStatus.FAILED:
            _save_history()
            return

    if not raw_mesh_path or not Path(raw_mesh_path).exists():
        with _jobs_lock:
            job["status"] = JobStatus.FAILED
            job["error"]  = "AI engine returned no mesh path."
        _save_history()
        return

    with _jobs_lock:
        job["original_url"] = f"/media/studio/outputs/{job_id}/{Path(raw_mesh_path).name}"
    p(65, f"Raw mesh saved: {Path(raw_mesh_path).name}")

    # ── 2. Load ───────────────────────────────────────────────────────────────
    with _jobs_lock:
        job["status"] = JobStatus.REPAIRING
    p(66, "Loading raw mesh…")
    try:
        raw = load_mesh(raw_mesh_path)
        p(67, f"Loaded: {len(raw.faces)} faces, {len(raw.vertices)} verts")
    except Exception as e:
        with _jobs_lock:
            job["status"] = JobStatus.FAILED
            job["error"]  = f"Could not load mesh: {e}"
        _save_history()
        return

    # ── 3. Repair ─────────────────────────────────────────────────────────────
    p(68, "Running mesh repair…")

    def rep_cb(pct, msg):
        with _jobs_lock:
            job["progress"] = 68 + int(pct * 0.12)
            job["log"].append(msg)

    try:
        repaired, repair_log = repair_mesh(raw, progress_cb=rep_cb)
        with _jobs_lock:
            job["log"].extend(repair_log)
        repaired_path = job_dir / f"{Path(raw_mesh_path).stem}_repaired.obj"
        raw_export = repaired.export(file_type='obj')
        if isinstance(raw_export, str):
            repaired_path.write_text(raw_export, encoding='utf-8')
        else:
            repaired_path.write_bytes(raw_export)
        with _jobs_lock:
            job["repaired_url"] = f"/media/studio/outputs/{job_id}/{repaired_path.name}"
        p(80, f"Repaired mesh saved ({len(repaired.faces)} faces).")
    except Exception as e:
        p(80, f"Repair failed: {e} — using raw mesh.")
        repaired = raw
        with _jobs_lock:
            job["repaired_url"] = job["original_url"]

    # ── 4. Validate ───────────────────────────────────────────────────────────
    with _jobs_lock:
        job["status"] = JobStatus.VALIDATING
    p(82, "Validating printability…")
    scale_to_mm = 1.0
    try:
        scale_to_mm = _scale_to_mm(
            repaired, params.get("unit", "mm"),
            params.get("size_x"), params.get("size_y"), params.get("size_z")
        )
        report = validate_mesh(repaired, unit=params.get("unit", "mm"), scale_to_mm=scale_to_mm)
        with _jobs_lock:
            job["validation"] = report.model_dump()
        p(88, f"Validation: {report.overall}")
    except Exception as e:
        p(88, f"Validation failed: {e}")

    # ── 5. Export ─────────────────────────────────────────────────────────────
    p(90, "Exporting…")
    stem    = Path(raw_mesh_path).stem + "_repaired"
    exports = {}
    for fmt in params.get("exports", ["stl", "obj", "glb"]):
        try:
            out = export_mesh(repaired, job_dir, stem, fmt, scale=scale_to_mm)
            exports[fmt] = f"/media/studio/outputs/{job_id}/{out.name}"
            p(90 + len(exports) * 2, f"Exported {fmt.upper()}")
        except Exception as e:
            p(90, f"Export {fmt} failed: {e}")

    with _jobs_lock:
        job["exports"]  = exports
        job["status"]   = JobStatus.COMPLETED
        job["progress"] = 100
    p(100, "Job complete.")
    _save_history()


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
def studio_index(request):
    ready, msg = ai_venv_ready()
    return render(request, 'studio/index.html', {
        'ai_ready': ready,
        'ai_msg':   msg,
    })


@login_required(login_url='login')
@require_POST
def upload_image(request):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'No file uploaded.'}, status=400)

    allowed = {'.jpg', '.jpeg', '.png', '.webp'}
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in allowed:
        return JsonResponse({'error': f'Unsupported type "{ext}". Allowed: jpg, jpeg, png, webp.'}, status=400)

    data = f.read()
    if len(data) > 20 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Max 20 MB.'}, status=413)

    try:
        from PIL import Image as PilImage
        PilImage.open(io.BytesIO(data)).verify()
    except Exception:
        return JsonResponse({'error': 'File is not a valid image.'}, status=400)

    uid  = uuid.uuid4().hex[:12]
    name = f"{uid}{ext}"
    (UPLOADS_DIR / name).write_bytes(data)
    return JsonResponse({'upload_id': uid, 'filename': name, 'size': len(data)})


@login_required(login_url='login')
@require_POST
def start_job(request):
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id":       job_id,
            "status":       JobStatus.QUEUED,
            "progress":     0,
            "log":          [],
            "filename":     body.get("filename", ""),
            "original_url": None,
            "repaired_url": None,
            "validation":   None,
            "exports":      {},
            "error":        None,
            "created":      time.time(),
        }

    t = threading.Thread(target=_run_job_thread, args=(job_id, body), daemon=True)
    t.start()
    return JsonResponse({"job_id": job_id, "status": JobStatus.QUEUED})


@login_required(login_url='login')
def poll_job(request, job_id):
    job = _job_or_404(job_id)
    if not job:
        return JsonResponse({'error': 'Job not found.'}, status=404)
    with _jobs_lock:
        return JsonResponse({
            "job_id":       job["job_id"],
            "status":       job["status"],
            "progress":     job["progress"],
            "original_url": job.get("original_url"),
            "repaired_url": job.get("repaired_url"),
            "validation":   job.get("validation"),
            "exports":      job.get("exports", {}),
            "error":        job.get("error"),
            "log":          job.get("log", []),
        })


@login_required(login_url='login')
def stream_job(request, job_id):
    """SSE endpoint — streams progress events until the job finishes."""
    if not _job_or_404(job_id):
        return JsonResponse({'error': 'Job not found.'}, status=404)

    def event_stream():
        last = 0
        while True:
            job = _job_or_404(job_id)
            if not job:
                break
            with _jobs_lock:
                new_logs = job["log"][last:]
                pct      = job["progress"]
                status   = job["status"]
            for msg in new_logs:
                yield f"data: {json.dumps({'msg': msg, 'pct': pct})}\n\n"
            last += len(new_logs)
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                yield f"data: {json.dumps({'done': True, 'status': status})}\n\n"
                break
            time.sleep(0.4)

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')


@login_required(login_url='login')
def job_history(request):
    if request.method == 'DELETE':
        with _jobs_lock:
            _jobs.clear()
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        return JsonResponse({'cleared': True})
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return JsonResponse({'jobs': history})


@login_required(login_url='login')
def download_export(request, job_id, fmt):
    job = _job_or_404(job_id)
    if not job:
        return JsonResponse({'error': 'Job not found.'}, status=404)
    with _jobs_lock:
        exports = job.get("exports", {})
    if fmt not in exports:
        return JsonResponse({'error': f'Format {fmt} not available.'}, status=404)
    rel = exports[fmt].lstrip('/')
    full = BASE_DIR / rel
    if not full.exists():
        return HttpResponseNotFound("Export file missing from disk.")
    return FileResponse(open(full, 'rb'), as_attachment=True, filename=full.name)


@login_required(login_url='login')
def health(request):
    ready, msg = ai_venv_ready()
    return JsonResponse({'ai_venv_ready': ready, 'ai_venv_msg': msg})
