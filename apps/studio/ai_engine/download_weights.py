"""
Download TripoSR weights. Run ONCE inside .venv_ai:
    .venv_ai\Scripts\python.exe apps\studio\ai_engine\download_weights.py
"""
import sys
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent.parent.parent
CACHE_DIR = ROOT / "model_weights" / "stabilityai--TripoSR"

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("ERROR: huggingface_hub not installed.")
    sys.exit(1)

print(f"Downloading TripoSR weights to: {CACHE_DIR}")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
try:
    path = snapshot_download(repo_id="stabilityai/TripoSR", cache_dir=str(CACHE_DIR),
                              ignore_patterns=["*.md", "*.txt"])
    print(f"Download complete: {path}")
except Exception as e:
    print(f"Download failed: {e}")
    sys.exit(1)
