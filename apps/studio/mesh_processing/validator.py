from __future__ import annotations
import logging
import numpy as np
import trimesh
from apps.studio.schemas import CheckResult, ValidationCheck, ValidationReport

log = logging.getLogger(__name__)


def validate_mesh(mesh: trimesh.Trimesh, unit: str = "mm", scale_to_mm: float = 1.0) -> ValidationReport:
    checks: list[ValidationCheck] = []
    warnings: list[str] = []

    def add(name, result, detail=""):
        checks.append(ValidationCheck(name=name, result=result, detail=detail))

    wt = mesh.is_watertight
    add("Watertight", CheckResult.PASS if wt else CheckResult.FAIL,
        "Mesh is a closed solid." if wt else "Mesh has open boundaries — not watertight.")

    try:
        n = len(mesh.split(only_watertight=False))
        add("Connected components", CheckResult.PASS if n == 1 else CheckResult.WARN,
            f"{n} component(s).")
    except Exception as e:
        add("Connected components", CheckResult.SKIPPED, str(e))

    try:
        n_b = len(mesh.boundary_edges) if hasattr(mesh, 'boundary_edges') else 0
        add("Boundary edges", CheckResult.PASS if n_b == 0 else CheckResult.FAIL,
            f"{n_b} boundary edge(s)." if n_b else "No open boundary edges.")
    except Exception as e:
        add("Boundary edges", CheckResult.SKIPPED, str(e))

    try:
        areas = trimesh.triangles.area(mesh.triangles)
        n_d = int((areas < 1e-10).sum())
        add("Degenerate faces", CheckResult.PASS if n_d == 0 else CheckResult.WARN,
            f"{n_d} degenerate face(s)." if n_d else "No degenerate faces.")
    except Exception as e:
        add("Degenerate faces", CheckResult.SKIPPED, str(e))

    try:
        ok = mesh.is_edge_manifold
        add("Non-manifold geometry", CheckResult.PASS if ok else CheckResult.FAIL,
            "All edges are manifold." if ok else "Non-manifold edges detected.")
    except Exception as e:
        add("Non-manifold geometry", CheckResult.SKIPPED, str(e))

    try:
        c = mesh.is_winding_consistent
        add("Normal / winding consistency", CheckResult.PASS if c else CheckResult.WARN,
            "Consistent winding." if c else "Inconsistent face winding.")
    except Exception as e:
        add("Normal / winding consistency", CheckResult.SKIPPED, str(e))

    add("Self-intersections", CheckResult.SKIPPED, "python-fcl not installed — skipped.")

    volume_mm3 = None
    try:
        v = float(mesh.volume)
        volume_mm3 = v * (scale_to_mm ** 3)
        add("Positive volume", CheckResult.PASS if v > 0 else CheckResult.FAIL,
            f"Volume ≈ {volume_mm3:,.1f} mm³." if v > 0 else f"Non-positive volume ({v:.4f}).")
    except Exception as e:
        add("Positive volume", CheckResult.SKIPPED, str(e))

    bbox_mm = None
    try:
        extents = mesh.extents * scale_to_mm
        bbox_mm = [round(float(x), 2) for x in extents]
        add("Bounding box", CheckResult.PASS,
            f"X={bbox_mm[0]:.1f} Y={bbox_mm[1]:.1f} Z={bbox_mm[2]:.1f} mm")
    except Exception as e:
        add("Bounding box", CheckResult.SKIPPED, str(e))

    min_wall_mm = None
    try:
        if mesh.is_watertight and len(mesh.faces) < 50000:
            min_wall_mm = _estimate_min_wall(mesh, scale_to_mm)
            ok = min_wall_mm >= 1.2
            add("Min wall thickness", CheckResult.PASS if ok else CheckResult.WARN,
                f"Estimated minimum ≈ {min_wall_mm:.2f} mm ({'ok' if ok else 'may be too thin'}).")
        else:
            add("Min wall thickness", CheckResult.SKIPPED, "Skipped — not watertight or too large.")
    except Exception as e:
        add("Min wall thickness", CheckResult.SKIPPED, str(e))

    results = [c.result for c in checks]
    overall = (CheckResult.FAIL if CheckResult.FAIL in results
               else CheckResult.WARN if CheckResult.WARN in results
               else CheckResult.PASS)

    def _get(name):
        for c in checks:
            if c.name == name:
                return c.result
        return CheckResult.SKIPPED

    return ValidationReport(
        overall=overall,
        watertight=_get("Watertight"),
        components=_get("Connected components"),
        boundary_edges=_get("Boundary edges"),
        degenerate_faces=_get("Degenerate faces"),
        non_manifold=_get("Non-manifold geometry"),
        normal_consistency=_get("Normal / winding consistency"),
        self_intersections=_get("Self-intersections"),
        volume_mm3=volume_mm3,
        bounding_box_mm=bbox_mm,
        min_wall_thickness_mm=min_wall_mm,
        checks=checks,
        warnings=warnings,
    )


def _estimate_min_wall(mesh: trimesh.Trimesh, scale_to_mm: float, n_rays: int = 50) -> float:
    centroids = mesh.triangles_center
    normals   = mesh.face_normals
    idx = np.random.choice(len(centroids), min(n_rays, len(centroids)), replace=False)
    origins    = centroids[idx] - normals[idx] * 1e-4
    directions = -normals[idx]
    locations, _, _ = mesh.ray.intersects_location(ray_origins=origins, ray_directions=directions)
    if len(locations) == 0:
        return float('inf')
    thicknesses = []
    for o, d in zip(origins, directions):
        diffs = locations - o
        dots  = (diffs * d).sum(axis=1)
        valid = dots[dots > 1e-5]
        if len(valid):
            thicknesses.append(float(valid.min()))
    if not thicknesses:
        return float('inf')
    return float(np.percentile(thicknesses, 5)) * scale_to_mm
