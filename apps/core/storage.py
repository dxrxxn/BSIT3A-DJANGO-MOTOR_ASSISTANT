"""Private storage helpers for user-uploaded diagnostic photos.

Uploaded images must never be served by Django's public ``MEDIA_URL``.
They are written to ``PRIVATE_MEDIA_ROOT`` and only exposed through an
authorisation-checked view.
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """File-system storage rooted outside the public media directory."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('location', settings.PRIVATE_MEDIA_ROOT)
        kwargs.setdefault('base_url', '/private-media/')
        super().__init__(*args, **kwargs)
