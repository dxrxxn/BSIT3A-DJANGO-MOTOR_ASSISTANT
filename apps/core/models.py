import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .storage import PrivateMediaStorage


# ---------------------------------------------------------------------------
# Existing offline knowledge cache and usage tracker
# ---------------------------------------------------------------------------

class JarvisKnowledge(models.Model):
    """
    Stores previous high-quality AI answers so JARVIS can still answer when
    the AI provider is unreachable.  It is a cache, not a verified manual.
    """
    user_query = models.CharField(max_length=500, db_index=True)
    clean_query = models.CharField(max_length=500, db_index=True, blank=True)
    keywords = models.TextField(blank=True, help_text="Space-separated normalized keywords")
    ai_response = models.TextField()
    hit_count = models.PositiveIntegerField(default=1)
    source = models.CharField(max_length=50, default='gemini')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Jarvis Offline Knowledge'
        verbose_name_plural = 'Jarvis Offline Knowledge'

    def __str__(self):
        return f"{self.user_query[:60]} ({self.hit_count} hits)"


class GeminiUsageTracker(models.Model):
    """
    Tracks requests made by this application against a locally configured
    daily budget.  This is NOT presented as the provider's current quota:
    Google's limits change by model and account tier.
    """
    date = models.DateField(default=timezone.now, unique=True)
    requests_count = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(default=0)
    candidates_tokens = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    # Kept for backwards compatibility with older templates/tests.  The live
    # value comes from settings.GEMINI_DAILY_REQUEST_LIMIT.
    DAILY_REQUEST_LIMIT = 1500

    @classmethod
    def daily_limit(cls):
        try:
            return max(1, int(getattr(settings, 'GEMINI_DAILY_REQUEST_LIMIT', cls.DAILY_REQUEST_LIMIT)))
        except (TypeError, ValueError):
            return cls.DAILY_REQUEST_LIMIT

    @classmethod
    def record_usage(cls, prompt_tokens=0, candidates_tokens=0):
        today = timezone.localdate()
        tracker, _ = cls.objects.get_or_create(date=today)
        tracker.requests_count += 1
        tracker.prompt_tokens += prompt_tokens
        tracker.candidates_tokens += candidates_tokens
        tracker.total_tokens += (prompt_tokens + candidates_tokens)
        tracker.save()
        return tracker

    @classmethod
    def get_current_quota(cls):
        today = timezone.localdate()
        tracker = cls.objects.filter(date=today).first()
        used = tracker.requests_count if tracker else 0
        tokens = tracker.total_tokens if tracker else 0
        limit = cls.daily_limit()
        remaining = max(0, limit - used)
        percent = max(0.0, round((remaining / limit) * 100, 1))
        return {
            'percent_left': percent,
            'requests_used': used,
            'requests_left': remaining,
            'requests_limit': limit,
            'tokens_today': tokens,
            'source': 'application_budget',
        }

    class Meta:
        ordering = ['-date']
        verbose_name = 'Gemini Usage Tracker'
        verbose_name_plural = 'Gemini Usage Trackers'

    def __str__(self):
        return f"{self.date}: {self.requests_count}/{self.daily_limit()} reqs ({self.total_tokens} tokens)"


# ---------------------------------------------------------------------------
# Conversation and diagnostic memory
# ---------------------------------------------------------------------------

class Conversation(models.Model):
    LANGUAGE_CHOICES = [
        ('auto', 'Auto detect'),
        ('english', 'English'),
        ('tagalog', 'Filipino / Tagalog'),
        ('hiligaynon', 'Hiligaynon / Ilonggo'),
    ]
    STATUS_CHOICES = [
        ('new', 'New'),
        ('identifying_vehicle', 'Identifying vehicle'),
        ('understanding_symptom', 'Understanding symptom'),
        ('safety_check', 'Safety check'),
        ('diagnosing', 'Diagnosing'),
        ('repair_guidance', 'Repair guidance'),
        ('verification', 'Verification'),
        ('closed', 'Closed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='diagnostic_conversations',
    )
    title = models.CharField(max_length=160, blank=True)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='auto')
    vehicle_type = models.CharField(max_length=20, blank=True)
    vehicle_make = models.CharField(max_length=80, blank=True)
    vehicle_model = models.CharField(max_length=120, blank=True)
    vehicle_year = models.CharField(max_length=10, blank=True)
    vehicle_variant = models.CharField(max_length=120, blank=True)
    engine_displacement = models.CharField(max_length=40, blank=True)
    fuel_system = models.CharField(max_length=30, blank=True)
    symptoms = models.TextField(blank=True)
    asked_questions = models.JSONField(default=list, blank=True)
    tests_attempted = models.JSONField(default=list, blank=True)
    findings = models.TextField(blank=True)
    stage = models.CharField(max_length=30, choices=STATUS_CHOICES, default='new')
    summary = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return self.title or f'Conversation {self.pk}'

    @property
    def vehicle_profile(self):
        return {
            'vehicle_type': self.vehicle_type or '',
            'make': self.vehicle_make or '',
            'model': self.vehicle_model or '',
            'year': self.vehicle_year or '',
            'variant': self.vehicle_variant or '',
            'engine_displacement': self.engine_displacement or '',
            'fuel_system': self.fuel_system or '',
        }

    def add_asked_questions(self, questions):
        known = [str(q).strip() for q in (self.asked_questions or []) if str(q).strip()]
        lowered = {q.lower() for q in known}
        for question in questions or []:
            text = str(question).strip()
            if text and text.lower() not in lowered:
                known.append(text)
                lowered.add(text.lower())
        # Keep memory bounded.
        self.asked_questions = known[-40:]

    def add_tests(self, tests):
        known = [str(t).strip() for t in (self.tests_attempted or []) if str(t).strip()]
        lowered = {t.lower() for t in known}
        for test in tests or []:
            text = str(test).strip()
            if text and text.lower() not in lowered:
                known.append(text)
                lowered.add(text.lower())
        self.tests_attempted = known[-30:]


class ChatTurn(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant'), ('system', 'System')]
    MODE_CHOICES = [
        ('ai', 'Gemini'),
        ('offline', 'Offline knowledge'),
        ('guided', 'Guided workflow'),
        ('legacy', 'Legacy engine'),
        ('error', 'Error'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='turns',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_turns',
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField(blank=True)
    language = models.CharField(max_length=20, blank=True)
    structured = models.JSONField(null=True, blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, blank=True)
    safety_severity = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['conversation', 'id'])]

    def __str__(self):
        return f'{self.role}: {self.content[:50]}'


# ---------------------------------------------------------------------------
# Diagnostic image uploads
# ---------------------------------------------------------------------------

def chat_upload_to(instance, filename):
    ext = os.path.splitext(filename or '')[1].lower()
    if ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
        ext = '.img'
    return f'chat_uploads/{instance.user_id or "anonymous"}/{uuid.uuid4().hex}{ext}'


class ImageUpload(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='diagnostic_uploads',
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='images',
    )
    file = models.FileField(storage=PrivateMediaStorage(), upload_to=chat_upload_to)
    original_name = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=80)
    size = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.original_name or f'Image {self.pk}'
