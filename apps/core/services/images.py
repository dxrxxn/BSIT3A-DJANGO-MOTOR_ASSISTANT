"""Private diagnostic photo intake.

Uploaded photos are untrusted input.  This module checks the real image
format with Pillow (not just the filename), bounds the decoded size, strips
EXIF orientation by transposing pixels, re-encodes to a web-safe JPEG, and
stores the result outside the public media tree.
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

try:  # Pillow is a declared requirement, but keep the site usable if it is missing.
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover - depends on deployment environment
    Image = None
    ImageOps = None
    UnidentifiedImageError = Exception

from apps.core.models import ImageUpload

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


class InvalidImageError(ValueError):
    """A public-safe upload error."""


@dataclass
class PreparedImage:
    data: bytes
    mime_type: str
    width: int
    height: int
    original_name: str


def _max_bytes():
    return max(1024, int(getattr(settings, 'IMAGE_UPLOAD_MAX_BYTES', 8 * 1024 * 1024)))


def _max_pixels():
    return max(10_000, int(getattr(settings, 'IMAGE_UPLOAD_MAX_PIXELS', 20_000_000)))


def _max_dimension():
    return max(400, int(getattr(settings, 'IMAGE_UPLOAD_MAX_DIMENSION', 1800)))


def _read_upload(upload):
    if upload is None:
        raise InvalidImageError('Choose a photo to upload.')
    size = getattr(upload, 'size', None)
    if size is not None and size > _max_bytes():
        raise InvalidImageError(
            f'The photo is too large. The limit is {_max_bytes() // (1024 * 1024)} MB.'
        )
    try:
        data = upload.read(_max_bytes() + 1)
    except (OSError, ValueError) as exc:
        raise InvalidImageError('The photo could not be read. Please choose another file.') from exc
    if not data:
        raise InvalidImageError('The uploaded file is empty.')
    if len(data) > _max_bytes():
        raise InvalidImageError(
            f'The photo is too large. The limit is {_max_bytes() // (1024 * 1024)} MB.'
        )
    return data


def prepare_image(upload):
    if Image is None:
        raise InvalidImageError(
            'Photo uploads are not available because the image library is not installed on this server.'
        )
    data = _read_upload(upload)
    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = (probe.format or '').upper()
            width, height = probe.size
            if image_format not in ALLOWED_FORMATS:
                raise InvalidImageError('Use a JPEG, PNG, or WebP photo.')
            if width <= 0 or height <= 0:
                raise InvalidImageError('The photo has invalid dimensions.')
            if width * height > _max_pixels():
                raise InvalidImageError('The photo dimensions are too large. Please resize it and try again.')
            probe.verify()
        # ``verify`` invalidates the decoder; reopen for the actual conversion.
        with Image.open(io.BytesIO(data)) as image:
            ImageOps.exif_transpose(image, in_place=True)
            image.load()
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                rgba = image.convert('RGBA')
                background = Image.new('RGB', rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.split()[-1])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')

            max_dimension = _max_dimension()
            if max(image.size) > max_dimension:
                image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            image.save(output, format='JPEG', quality=88, optimize=True, progressive=True)
            prepared_data = output.getvalue()
            output_width, output_height = image.size
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError(
            'That file is not a readable JPEG, PNG, or WebP image.'
        ) from exc

    original_name = os.path.basename(getattr(upload, 'name', '') or 'photo.jpg')[:255]
    stem, extension = os.path.splitext(original_name)
    if extension.lower() not in ALLOWED_EXTENSIONS:
        stem = stem or 'photo'
    # The stored bytes are always re-encoded as JPEG, so keep the display name
    # and stored file extension consistent with the actual format.
    original_name = f'{(stem or "photo")[:240]}.jpg'
    return PreparedImage(
        data=prepared_data,
        mime_type='image/jpeg',
        width=output_width,
        height=output_height,
        original_name=original_name,
    )


@transaction.atomic
def save_uploaded_image(user, upload, *, conversation=None, description=''):
    prepared = prepare_image(upload)
    record = ImageUpload(
        user=user,
        conversation=conversation,
        original_name=prepared.original_name,
        mime_type=prepared.mime_type,
        size=len(prepared.data),
        width=prepared.width,
        height=prepared.height,
        description=(description or '')[:2000],
    )
    record.file.save(
        os.path.basename(prepared.original_name),
        ContentFile(prepared.data),
        save=False,
    )
    record.save()
    return record


def attach_to_conversation(image, conversation, user):
    if image is None or conversation is None:
        return image
    if image.user_id != user.id:
        raise InvalidImageError('That photo does not belong to this account.')
    if image.conversation_id and image.conversation_id != conversation.id:
        raise InvalidImageError('That photo belongs to a different conversation.')
    if not image.conversation_id:
        image.conversation = conversation
        image.save(update_fields=['conversation'])
    return image
