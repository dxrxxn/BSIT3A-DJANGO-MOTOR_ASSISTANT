"""
Motor app views — 3D viewer + image-to-GLB reconstruction.
"""
import os
import json
import logging
import re
import uuid
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.conf import settings

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _safe_name(filename: str) -> str:
    """Keep only alphanumeric, dot, hyphen, underscore."""
    return ''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)


def _scan_models(models_dir: str) -> list[dict]:
    """Return a list of model dicts for all supported files in models_dir."""
    exts = ('.glb', '.gltf', '.jpg', '.jpeg', '.png')
    result = []
    if os.path.isdir(models_dir):
        for fname in sorted(os.listdir(models_dir)):
            if fname.lower().endswith(exts):
                result.append({
                    'name': fname,
                    'url': settings.MEDIA_URL + 'models/' + fname,
                    'label': (
                        os.path.splitext(fname)[0]
                        .replace('_', ' ')
                        .replace('-', ' ')
                        .title()
                    ),
                })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
def viewer_3d(request):
    """Render the interactive 3D viewer page."""
    models_dir = os.path.join(settings.MEDIA_ROOT, 'models')
    model_files = _scan_models(models_dir)
    return render(request, 'motor/viewer_3d.html', {
        'model_files': json.dumps(model_files),
    })


@login_required(login_url='login')
@require_POST
def upload_model(request):
    """
    Accept a GLB/GLTF upload and save to media/models/.
    JPG/PNG uploads are also accepted but NOT auto-converted here —
    conversion happens via reconstruct_3d.
    """
    uploaded = request.FILES.get('model_file')
    if not uploaded:
        return JsonResponse({'error': 'No file uploaded.'}, status=400)

    allowed_ext = ('.glb', '.gltf', '.jpg', '.jpeg', '.png')
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in allowed_ext:
        return JsonResponse(
            {'error': f'Unsupported file type "{ext}". Allowed: GLB, GLTF, JPG, PNG.'},
            status=400,
        )

    max_size = 50 * 1024 * 1024 if ext in ('.glb', '.gltf') else 10 * 1024 * 1024
    if uploaded.size > max_size:
        limit = '50 MB' if ext in ('.glb', '.gltf') else '10 MB'
        return JsonResponse({'error': f'File too large. Maximum size is {limit}.'}, status=400)

    models_dir = os.path.join(settings.MEDIA_ROOT, 'models')
    os.makedirs(models_dir, exist_ok=True)

    safe_name = _safe_name(uploaded.name)
    dest_path = os.path.join(models_dir, safe_name)
    with open(dest_path, 'wb') as fh:
        for chunk in uploaded.chunks():
            fh.write(chunk)

    is_image = ext in ('.jpg', '.jpeg', '.png')
    return JsonResponse({
        'status': 'ok',
        'url': settings.MEDIA_URL + 'models/' + safe_name,
        'name': safe_name,
        'label': os.path.splitext(safe_name)[0].replace('_', ' ').replace('-', ' ').title(),
        'is_image': is_image,
    })


@login_required(login_url='login')
@require_POST
def delete_model_image(request):
    """Delete an image and any 3D reconstruction generated from it."""
    name = request.POST.get('name', '')
    if (
        not name
        or name in ('.', '..')
        or _safe_name(name) != name
        or Path(name).suffix.lower() not in ('.jpg', '.jpeg', '.png')
    ):
        return JsonResponse({'error': 'Invalid image name.'}, status=400)

    models_dir = (Path(settings.MEDIA_ROOT) / 'models').resolve()
    image_path = models_dir / name
    if image_path.is_symlink():
        return JsonResponse({'error': 'Invalid image path.'}, status=400)
    if not image_path.is_file():
        return JsonResponse({'error': 'Image not found.'}, status=404)

    related_paths = []
    generated_source = re.fullmatch(r'src_([0-9a-f]{8})_(.+)', name, re.IGNORECASE)
    if generated_source:
        uid, source_name = generated_source.groups()
        related_paths.append(models_dir / f'recon_{uid}_{Path(source_name).stem}.glb')
    else:
        source_pattern = re.compile(
            rf'^src_([0-9a-f]{{8}})_{re.escape(name)}$',
            re.IGNORECASE,
        )
        for candidate in models_dir.iterdir():
            match = source_pattern.fullmatch(candidate.name)
            if match:
                uid = match.group(1)
                related_paths.extend((
                    candidate,
                    models_dir / f'recon_{uid}_{Path(name).stem}.glb',
                ))

    paths_to_delete = [image_path, *dict.fromkeys(related_paths)]
    if any(path.is_symlink() for path in paths_to_delete):
        return JsonResponse({'error': 'Invalid image path.'}, status=400)

    try:
        for path in paths_to_delete:
            if path.is_file():
                path.unlink()
    except OSError:
        log.exception('Failed to delete viewer image or reconstruction for %s', image_path)
        return JsonResponse({'error': 'Could not delete the image and its 3D reconstruction.'}, status=500)

    return JsonResponse({
        'status': 'ok',
        'deleted_names': [path.name for path in paths_to_delete],
    })


@login_required(login_url='login')
@require_POST
def reconstruct_3d(request):
    """
    Convert an uploaded JPG/PNG to a GLB using the server-side pipeline.

    POST params
    -----------
    model_file  : image file
    mesh_res    : int  100–400  (default 200)
    depth_scale : float 0.05–0.8 (default 0.35)
    """
    # ── Import here so startup isn't blocked if libs are missing ──
    try:
        from apps.motor.reconstruct import image_to_glb
    except ImportError as exc:
        log.exception('reconstruct module unavailable')
        return JsonResponse(
            {'error': f'Reconstruction library not available: {exc}'},
            status=503,
        )

    uploaded = request.FILES.get('model_file')
    if not uploaded:
        return JsonResponse({'error': 'No file uploaded.'}, status=400)

    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png'):
        return JsonResponse(
            {'error': 'Only JPG or PNG images can be converted to 3D.'},
            status=400,
        )

    if uploaded.size > 15 * 1024 * 1024:
        return JsonResponse({'error': 'Image too large. Maximum 15 MB.'}, status=400)

    # Parse options
    try:
        mesh_res = int(request.POST.get('mesh_res', 200))
        mesh_res = max(80, min(400, mesh_res))
    except (TypeError, ValueError):
        mesh_res = 200

    try:
        depth_scale = float(request.POST.get('depth_scale', 0.35))
        depth_scale = max(0.05, min(0.80, depth_scale))
    except (TypeError, ValueError):
        depth_scale = 0.35

    # Save the source image
    models_dir = Path(settings.MEDIA_ROOT) / 'models'
    models_dir.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex[:8]
    safe_img = _safe_name(uploaded.name)
    img_path = models_dir / f'src_{uid}_{safe_img}'
    with open(img_path, 'wb') as fh:
        for chunk in uploaded.chunks():
            fh.write(chunk)

    # Output GLB path
    glb_stem = os.path.splitext(safe_img)[0]
    glb_name = f'recon_{uid}_{glb_stem}.glb'
    glb_path = models_dir / glb_name

    try:
        stats = image_to_glb(
            img_path,
            glb_path,
            mesh_res=mesh_res,
            depth_scale=depth_scale,
            tex_size=1024,
        )
    except Exception as exc:
        log.exception('image_to_glb failed for %s', img_path)
        return JsonResponse(
            {'error': f'Reconstruction failed: {exc}'},
            status=500,
        )

    glb_url = settings.MEDIA_URL + 'models/' + glb_name
    label = glb_stem.replace('_', ' ').replace('-', ' ').title() + ' (3D)'

    return JsonResponse({
        'status': 'ok',
        'url': glb_url,
        'name': glb_name,
        'label': label,
        'faces': stats['faces'],
        'vertices': stats['vertices'],
        'warnings': stats['warnings'],
    })
