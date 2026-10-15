from __future__ import annotations
import logging
from copy import deepcopy
from pathlib import Path
import trimesh

log = logging.getLogger(__name__)
SUPPORTED = ("stl", "obj", "ply", "glb")


def export_mesh(mesh: trimesh.Trimesh, dest_dir: str | Path, stem: str, fmt: str, scale: float = 1.0) -> Path:
    fmt = fmt.lower().strip(".")
    if fmt not in SUPPORTED:
        raise ValueError(f"Unsupported export format '{fmt}'. Choose from: {SUPPORTED}")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / f"{stem}.{fmt}"
    m = deepcopy(mesh)
    if scale != 1.0:
        m.apply_scale(scale)
    raw = m.export(file_type=fmt)
    if isinstance(raw, str):
        out_path.write_text(raw, encoding='utf-8')
    else:
        out_path.write_bytes(raw)
    log.info("Exported %s (%d bytes)", out_path, out_path.stat().st_size)
    _validate_export(out_path, len(m.faces), fmt)
    return out_path


def _validate_export(path: Path, expected_faces: int, fmt: str) -> None:
    try:
        back = trimesh.load(str(path), force='mesh')
        if isinstance(back, trimesh.Scene):
            meshes = list(back.geometry.values())
            if meshes:
                back = trimesh.util.concatenate(meshes)
        if isinstance(back, trimesh.Trimesh):
            got = len(back.faces)
            if abs(got - expected_faces) > max(1, expected_faces * 0.01):
                log.warning("Export mismatch %s: expected %d faces, got %d.", path.name, expected_faces, got)
    except Exception as e:
        log.warning("Export validation failed for %s: %s", path.name, e)
