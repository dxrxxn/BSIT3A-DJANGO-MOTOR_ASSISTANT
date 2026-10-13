"""
reconstruct.py — Server-side image-to-3D pipeline.

Why the old approach looked "melted"
-------------------------------------
The previous code used raw pixel luminance as the Z displacement:
    z = (brightness / 255) * depth

That treats bright = front, dark = back, so a bright sky becomes a
spike and a dark object edge becomes a pit.  The mesh looks melted
because luminance has nothing to do with actual depth.

This module fixes the root cause with three blended depth cues:
  A) Luminance — objects are often brighter than backgrounds
  B) Edge-saliency ridge — object boundaries have strong gradients;
     blurring the edge map gives each boundary a "raised ridge" that
     follows the actual silhouette of the object
  C) Centroid weight — objects tend to be centred; distant corners
     are pulled back slightly

The blend is then Gaussian-smoothed (to remove noise) while a
detail-sharpening pass re-adds the high-frequency signal so bolts,
fins, and grooves are preserved.

No PyTorch, no Blender, no GPU required.
"""

import io
import logging
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from scipy.ndimage import gaussian_filter
import trimesh
from trimesh.visual.texture import TextureVisuals
from trimesh.visual.material import PBRMaterial

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def image_to_glb(
    src_path: str | Path,
    dst_path: str | Path,
    *,
    mesh_res: int = 200,
    depth_scale: float = 0.35,
    tex_size: int = 1024,
) -> dict:
    """
    Convert an image file to a GLB 3D mesh.

    Parameters
    ----------
    src_path    : path to the input image (JPG / PNG)
    dst_path    : where to write the output .glb
    mesh_res    : grid resolution — number of quads along the longer axis
    depth_scale : max displacement in model-space units (0.05 – 0.80)
    tex_size    : texture image resolution (pixels on the longer side)

    Returns
    -------
    dict  { faces: int, vertices: int, warnings: list[str] }
    """
    src_path = Path(src_path)
    dst_path = Path(dst_path)

    # 1 ── Load + correct EXIF rotation
    img_pil = _load_and_orient(src_path)
    orig_w, orig_h = img_pil.size

    # 2 ── Build texture-resolution image (preserves detail for UV map)
    scale = tex_size / max(orig_w, orig_h)
    tw = max(4, int(orig_w * scale))
    th = max(4, int(orig_h * scale))
    img_tex = img_pil.resize((tw, th), Image.LANCZOS).convert('RGB')

    # 3 ── Build mesh-resolution thumbnail (faster depth processing)
    asp = orig_w / orig_h
    if asp >= 1.0:
        mw = mesh_res + 1
        mh = max(4, int(mw / asp))
    else:
        mh = mesh_res + 1
        mw = max(4, int(mh * asp))
    img_small = img_tex.resize((mw, mh), Image.LANCZOS)

    # 4 ── Depth estimation
    depth = _estimate_depth(img_small, depth_scale)

    # 5 ── Build front-face mesh
    verts, faces, uvs = _build_mesh(depth, mw, mh)

    # 6 ── Add a flat back plate so it's not a single-sided sheet
    verts, faces, uvs = _add_back_face(verts, faces, uvs, depth_scale)

    # 7 ── Package as trimesh with PBR texture
    tex_bytes = _pil_to_png_bytes(img_tex)
    mesh = _build_trimesh(verts, faces, uvs, tex_bytes)

    # 8 ── Quality check
    warnings = _quality_check(mesh, depth)

    # 9 ── Export GLB
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    glb_bytes = _export_glb(mesh)
    dst_path.write_bytes(glb_bytes)

    log.info("GLB written: %s  verts=%d  faces=%d", dst_path, len(verts), len(faces))
    return {
        'faces': len(faces),
        'vertices': len(verts),
        'warnings': warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_and_orient(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img.convert('RGBA')


def _estimate_depth(img: Image.Image, depth_scale: float) -> np.ndarray:
    """
    Produce a plausible depth field in [0, depth_scale].

    Blends three cues:
      A  Luminance          (objects tend to be brighter than backgrounds)
      B  Edge-saliency ridge (borders of objects produce raised ridges)
      C  Centre-proximity   (objects tend to be centred in the frame)
    """
    arr = np.array(img.convert('RGB'), dtype=np.float32) / 255.0
    h, w = arr.shape[:2]

    # ── A: luminance ────────────────────────────────────────────
    lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]

    # ── B: edge-saliency ridge ──────────────────────────────────
    pil_gray = Image.fromarray((lum * 255).astype(np.uint8))
    edge_arr = np.array(pil_gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32) / 255.0
    # Blur the raw edges into a smooth ridge shape
    ridge_sigma = max(2.0, min(w, h) * 0.018)
    edge_ridge = gaussian_filter(edge_arr, sigma=ridge_sigma)

    # ── C: centre proximity ─────────────────────────────────────
    yy = np.linspace(-1.0, 1.0, h, dtype=np.float32)
    xx = np.linspace(-1.0, 1.0, w, dtype=np.float32)
    xx, yy = np.meshgrid(xx, yy)
    dist = np.sqrt(xx ** 2 + yy ** 2)
    centre_w = np.clip(1.0 - dist * 0.8, 0.0, 1.0)

    # ── Blend ───────────────────────────────────────────────────
    depth_raw = 0.45 * lum + 0.35 * edge_ridge + 0.20 * centre_w

    # ── Smooth to remove sensor/compression noise ────────────────
    sigma_smooth = max(1.2, min(w, h) * 0.014)
    depth_smooth = gaussian_filter(depth_raw, sigma=sigma_smooth)

    # ── Re-add sharpened detail (preserves fins, bolts, grooves) ─
    sigma_detail = max(0.6, min(w, h) * 0.005)
    detail = depth_raw - gaussian_filter(depth_raw, sigma=sigma_detail * 8)
    depth_blend = depth_smooth + 0.28 * detail

    # ── Normalise to [0, 1] ──────────────────────────────────────
    lo, hi = float(depth_blend.min()), float(depth_blend.max())
    if hi - lo < 1e-6:
        return np.zeros((h, w), dtype=np.float32)
    depth_n = (depth_blend - lo) / (hi - lo)

    # ── Use alpha channel to suppress background ─────────────────
    if img.mode == 'RGBA':
        alpha = np.array(img.split()[3], dtype=np.float32) / 255.0
        alpha_s = gaussian_filter(alpha, sigma=sigma_smooth * 0.6)
        depth_n = depth_n * alpha_s

    return (depth_n * depth_scale).astype(np.float32)


def _build_mesh(depth: np.ndarray, w: int, h: int):
    """
    Build a displaced quad mesh from a depth field.

    Coordinate system
    -----------------
    X : [-aspect/2,  +aspect/2]  (width)
    Y : [-0.5,       +0.5]       (height, Y-up)
    Z : [0,          depth_scale] (depth toward viewer)
    """
    aspect = w / h
    xs = np.linspace(-aspect / 2.0,  aspect / 2.0, w, dtype=np.float32)
    ys = np.linspace(0.5,            -0.5,          h, dtype=np.float32)

    xx, yy = np.meshgrid(xs, ys)          # (h, w)
    zz = depth                             # (h, w)
    verts = np.stack([xx.ravel(), yy.ravel(), zz.ravel()], axis=1)  # (h*w, 3)

    # UV  (V flipped so image is right-side up in the viewer)
    uu = np.linspace(0.0, 1.0, w, dtype=np.float32)
    vv = np.linspace(0.0, 1.0, h, dtype=np.float32)
    uu_g, vv_g = np.meshgrid(uu, vv)
    uvs = np.stack([uu_g.ravel(), 1.0 - vv_g.ravel()], axis=1)

    # Quad → 2 triangles (CCW winding, front face toward +Z)
    ri = np.arange(h - 1, dtype=np.int32)
    ci = np.arange(w - 1, dtype=np.int32)
    ri, ci = np.meshgrid(ri, ci, indexing='ij')
    ri, ci = ri.ravel(), ci.ravel()

    tl = ri * w + ci
    tr = ri * w + (ci + 1)
    bl = (ri + 1) * w + ci
    br = (ri + 1) * w + (ci + 1)

    faces = np.concatenate([
        np.stack([tl, bl, tr], axis=1),
        np.stack([tr, bl, br], axis=1),
    ], axis=0).astype(np.int32)

    return verts, faces, uvs


def _add_back_face(verts, faces, uvs, depth_scale: float):
    """
    Append a flat back plate slightly behind Z=0 so the model is not
    a single translucent sheet when viewed from the side.
    """
    xmin, ymin = float(verts[:, 0].min()), float(verts[:, 1].min())
    xmax, ymax = float(verts[:, 0].max()), float(verts[:, 1].max())
    z_back = float(-depth_scale * 0.04)

    back_verts = np.array([
        [xmin, ymin, z_back],
        [xmax, ymin, z_back],
        [xmax, ymax, z_back],
        [xmin, ymax, z_back],
    ], dtype=np.float32)

    base = len(verts)
    back_uvs = np.array([
        [0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0],
    ], dtype=np.float32)

    # CW winding so back plate faces away from viewer
    back_faces = np.array([
        [base + 0, base + 2, base + 1],
        [base + 0, base + 3, base + 2],
    ], dtype=np.int32)

    return (
        np.concatenate([verts, back_verts], axis=0),
        np.concatenate([faces, back_faces], axis=0),
        np.concatenate([uvs,   back_uvs],  axis=0),
    )


def _build_trimesh(verts, faces, uvs, tex_bytes: bytes) -> trimesh.Trimesh:
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    mesh.visual = TextureVisuals(
        uv=uvs,
        material=PBRMaterial(
            baseColorTexture=Image.open(io.BytesIO(tex_bytes)),
            metallicFactor=0.15,
            roughnessFactor=0.65,
            doubleSided=True,
        ),
    )
    mesh.rezero()
    return mesh


def _pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=False)
    return buf.getvalue()


def _export_glb(mesh: trimesh.Trimesh) -> bytes:
    scene = trimesh.Scene(geometry={'mesh': mesh})
    return scene.export(file_type='glb')


def _quality_check(mesh: trimesh.Trimesh, depth: np.ndarray) -> list:
    warnings = []
    if len(mesh.vertices) == 0:
        warnings.append('Mesh has zero vertices.')
        return warnings
    d_std  = float(depth.std())
    d_mean = float(depth.mean())
    if d_mean > 0 and d_std > d_mean * 2.5:
        warnings.append(
            f'High depth variance (std={d_std:.3f} mean={d_mean:.3f}). '
            'Try a lower depth value.'
        )
    if hasattr(mesh, 'triangles') and len(mesh.triangles):
        areas   = trimesh.triangles.area(mesh.triangles)
        n_degen = int((areas < 1e-10).sum())
        if n_degen:
            warnings.append(f'{n_degen} degenerate triangles.')
    return warnings
