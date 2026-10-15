"""
TripoSR runner — runs inside .venv_ai (Python 3.11 + PyTorch).
Called by worker.py as a subprocess. Prints JSON progress to stdout.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

def emit(data: dict) -> None:
    print(json.dumps(data), flush=True)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image",  required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--chunk-size", type=int, default=8192)
    args = parser.parse_args()

    image_path = Path(args.image)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    emit({"type": "progress", "pct": 2, "msg": "Detecting hardware…"})
    try:
        import torch
        device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device
        if device == "cuda":
            vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            emit({"type": "progress", "pct": 3, "msg": f"GPU: {torch.cuda.get_device_name(0)} ({vram:.1f} GB VRAM)"})
            if vram < 4.5:
                args.chunk_size = 2048
                emit({"type": "progress", "pct": 3, "msg": "WARNING: VRAM < 4.5 GB — using smaller chunks."})
        else:
            emit({"type": "progress", "pct": 3, "msg": "CPU mode — inference will be slow (5–20 min)."})
    except ImportError:
        emit({"type": "error", "msg": "PyTorch not found. Install requirements_ai.txt in .venv_ai."})
        sys.exit(1)

    emit({"type": "progress", "pct": 5, "msg": "Loading TripoSR model…"})
    try:
        ROOT = Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(ROOT / "TripoSR"))
        from tsr.system import TSR
        from tsr.utils import remove_background, resize_foreground
    except ImportError as e:
        emit({"type": "error", "msg": f"TripoSR not found: {e}. Clone https://github.com/VAST-AI-Research/TripoSR to project root."})
        sys.exit(1)

    model_dir = ROOT / "model_weights" / "stabilityai--TripoSR"
    try:
        model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml",
                                     weight_name="model.ckpt", cache_dir=str(model_dir))
        model.renderer.set_chunk_size(args.chunk_size)
        model = model.to(device)
    except Exception as e:
        emit({"type": "error", "msg": f"Model load failed: {e}. Run: python apps/studio/ai_engine/download_weights.py"})
        sys.exit(1)

    emit({"type": "progress", "pct": 20, "msg": "Preprocessing image…"})
    try:
        from PIL import Image
        img = Image.open(str(image_path)).convert("RGBA")
        img = remove_background(img)
        img = resize_foreground(img, ratio=0.85)
        img = img.convert("RGB").resize((512, 512))
    except Exception as e:
        emit({"type": "error", "msg": f"Image preprocessing failed: {e}"}); sys.exit(1)

    emit({"type": "progress", "pct": 35, "msg": "Running TripoSR inference…"})
    try:
        import torch
        with torch.no_grad():
            scene_codes = model([img], device=device)
    except torch.cuda.OutOfMemoryError:
        emit({"type": "error", "msg": "GPU out of memory. Try --device cpu or reduce chunk size."})
        sys.exit(1)
    except Exception as e:
        emit({"type": "error", "msg": f"Inference failed: {e}"}); sys.exit(1)

    emit({"type": "progress", "pct": 75, "msg": "Extracting mesh…"})
    try:
        meshes = model.extract_mesh(scene_codes, resolution=256)
        raw_mesh = meshes[0]
    except Exception as e:
        emit({"type": "error", "msg": f"Mesh extraction failed: {e}"}); sys.exit(1)

    emit({"type": "progress", "pct": 90, "msg": "Saving raw mesh…"})
    try:
        obj_path = output_dir / f"{image_path.stem}_raw.obj"
        raw_mesh.export(str(obj_path))
    except Exception as e:
        emit({"type": "error", "msg": f"Export failed: {e}"}); sys.exit(1)

    emit({"type": "progress", "pct": 100, "msg": "TripoSR complete."})
    emit({"type": "result", "mesh_path": str(obj_path)})

if __name__ == "__main__":
    main()
