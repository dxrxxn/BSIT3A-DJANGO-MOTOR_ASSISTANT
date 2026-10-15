from __future__ import annotations
import logging
from copy import deepcopy
from typing import Callable
import numpy as np
import trimesh
import trimesh.repair

log = logging.getLogger(__name__)

def repair_mesh(
    mesh: trimesh.Trimesh,
    progress_cb: Callable[[int, str], None] | None = None,
) -> tuple[trimesh.Trimesh, list[str]]:
    mesh = deepcopy(mesh)
    log_lines: list[str] = []

    def step(pct: int, msg: str) -> None:
        log_lines.append(msg)
        if progress_cb:
            progress_cb(pct, msg)

    step(5,  "Stage 1: Checking for NaN / infinite vertices…")
    try:
        finite_mask = np.isfinite(mesh.vertices).all(axis=1)
        bad = int((~finite_mask).sum())
        if bad:
            mesh.remove_vertices(np.where(~finite_mask)[0])
            step(5, f"  Removed {bad} non-finite vertices.")
        else:
            step(5, "  No non-finite vertices found.")
    except Exception as e:
        step(5, f"  NaN check failed: {e}")

    step(15, "Stage 2: Removing degenerate faces…")
    try:
        before = len(mesh.faces)
        trimesh.repair.fix_winding(mesh)
        mesh.remove_degenerate_faces()
        mesh.remove_duplicate_faces()
        step(15, f"  Removed {before - len(mesh.faces)} degenerate/duplicate faces.")
    except Exception as e:
        step(15, f"  Degenerate face removal failed: {e}")

    step(25, "Stage 3: Merging duplicate vertices…")
    try:
        before = len(mesh.vertices)
        mesh.merge_vertices()
        step(25, f"  Merged vertices: {before} → {len(mesh.vertices)}.")
    except Exception as e:
        step(25, f"  Vertex merge failed: {e}")

    step(35, "Stage 4: Fixing face winding / normals…")
    try:
        trimesh.repair.fix_winding(mesh)
        trimesh.repair.fix_normals(mesh)
        step(35, "  Face winding and normals fixed.")
    except Exception as e:
        step(35, f"  Winding fix failed: {e}")

    step(50, "Stage 5: Detecting and filling holes…")
    try:
        boundary = trimesh.repair.fill_holes(mesh)
        step(50, f"  Filled {boundary} hole(s)." if boundary else "  No holes or fill not possible.")
    except Exception as e:
        step(50, f"  Hole fill failed: {e}")

    step(65, "Stage 6: Checking connected components…")
    try:
        components = mesh.split(only_watertight=False)
        n = len(components)
        if n > 1:
            biggest = max(components, key=lambda m: len(m.faces))
            removed = sum(len(c.faces) for c in components if c is not biggest)
            step(65, f"  {n} components — keeping largest ({len(biggest.faces)} faces), removing {removed} faces.")
            mesh = biggest
        else:
            step(65, "  Single connected component.")
    except Exception as e:
        step(65, f"  Component split failed: {e}")

    step(80, "Stage 7: Final normal recalculation…")
    try:
        mesh.fix_normals()
        step(80, "  Normals recalculated.")
    except Exception as e:
        step(80, f"  Normal recalc failed: {e}")

    step(90, "Stage 8: Checking volume…")
    try:
        vol = mesh.volume
        if vol < 0:
            mesh.invert()
            step(90, f"  Volume was negative — mesh inverted.")
        else:
            step(90, f"  Volume: {vol:.4f} units³.")
    except Exception as e:
        step(90, f"  Volume check failed: {e}")

    step(100, "Repair pipeline complete.")
    return mesh, log_lines
