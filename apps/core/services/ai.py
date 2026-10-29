"""Centralised Gemini access for the diagnostic assistant.

Only this module talks to the AI provider.  It keeps credentials on the
server, classifies failures for friendly user messages, uses the SDK's bounded
retry policy for retryable HTTP statuses, and never returns raw provider
errors to the browser.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class AiServiceError(Exception):
    category = 'unavailable'
    public_message = 'The AI service is unavailable right now. Local repair knowledge can still help.'

    def __init__(self, message='', *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class AiNotConfigured(AiServiceError):
    category = 'not_configured'
    public_message = 'Gemini is not configured on this server. Offline repair knowledge is being used.'


class AiAuthError(AiServiceError):
    category = 'auth'
    public_message = 'The AI credentials were rejected. Ask the project administrator to check the server configuration.'


class AiQuotaExceeded(AiServiceError):
    category = 'quota'
    public_message = 'The configured AI request budget is exhausted. Offline repair knowledge is being used.'


class AiRateLimited(AiServiceError):
    category = 'rate_limit'
    public_message = 'The AI service is temporarily rate-limited. Please retry shortly; offline repair knowledge is available now.'


class AiTimeout(AiServiceError):
    category = 'timeout'
    public_message = 'The AI service took too long to respond. Offline repair knowledge is being used.'


class AiServerError(AiServiceError):
    category = 'server'
    public_message = 'The AI service had a temporary server problem. Offline repair knowledge is being used.'


class AiInvalidRequest(AiServiceError):
    category = 'invalid_request'
    public_message = 'The configured AI model rejected this request. Offline repair knowledge is being used.'


@dataclass
class AiResult:
    text: str = ''
    structured: dict | None = None
    model: str = ''
    usage: dict = field(default_factory=dict)
    raw_finish_reason: str = ''


def model_name():
    """Return the configured Gemini model, without a ``models/`` prefix."""
    return (
        getattr(settings, 'GEMINI_MODEL', '')
        or getattr(settings, 'AI_MODEL', '')
        or ''
    ).strip().replace('models/', '')


def _daily_budget_remaining():
    from apps.core.models import GeminiUsageTracker
    quota = GeminiUsageTracker.get_current_quota()
    return quota['requests_left'] > 0


def is_ai_configured():
    return bool(getattr(settings, 'GEMINI_API_KEY', '')) and bool(model_name())


def is_ai_available():
    """True when a configured key can be used within the app's own budget."""
    if not is_ai_configured():
        return False
    try:
        return _daily_budget_remaining()
    except Exception:
        return True


def _make_client():
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise AiNotConfigured()
    model = model_name()
    if not model:
        raise AiNotConfigured('No Gemini model configured.')
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise AiNotConfigured('google-genai is not installed.') from exc

    timeout_ms = max(1000, int(getattr(settings, 'GEMINI_TIMEOUT_SECONDS', 45)) * 1000)
    attempts = max(1, int(getattr(settings, 'GEMINI_MAX_RETRIES', 3)))
    retry_options = types.HttpRetryOptions(
        attempts=attempts,
        initial_delay=1,
        max_delay=8,
        exp_base=2,
        jitter=0.2,
        http_status_codes=[429, 500, 502, 503, 504],
    )
    http_options = types.HttpOptions(timeout=timeout_ms, retry_options=retry_options)
    return genai.Client(api_key=api_key, http_options=http_options), types


def _classify_exception(exc):
    """Map SDK/network failures to a small set of safe public categories."""
    status = getattr(exc, 'status_code', None) or getattr(exc, 'code', None)
    if status is None:
        response = getattr(exc, 'response', None)
        status = getattr(response, 'status_code', None)
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None

    text = f'{type(exc).__name__} {exc}'.lower()
    if status in (401, 403):
        return AiAuthError(status_code=status)
    if status == 404:
        return AiInvalidRequest('Configured model was not found.', status_code=status)
    if status == 429:
        if 'quota' in text or 'billing' in text or 'exhausted' in text:
            return AiQuotaExceeded(status_code=status)
        return AiRateLimited(status_code=status)
    if status in (400, 422):
        return AiInvalidRequest(status_code=status)
    if status is not None and 500 <= status <= 599:
        return AiServerError(status_code=status)
    if any(marker in text for marker in ('timeout', 'timed out', 'deadline')):
        return AiTimeout(status_code=status)
    if any(marker in text for marker in ('quota', 'resource_exhausted')):
        return AiQuotaExceeded(status_code=status)
    if any(marker in text for marker in ('connection', 'network', 'dns', 'ssl')):
        return AiServiceError(status_code=status)
    return AiServiceError(status_code=status)


def _extract_usage(response):
    meta = getattr(response, 'usage_metadata', None)
    if meta is None:
        return {'prompt_tokens': 0, 'candidates_tokens': 0, 'total_tokens': 0}
    prompt = getattr(meta, 'prompt_token_count', 0) or 0
    candidates = getattr(meta, 'candidates_token_count', 0) or 0
    return {
        'prompt_tokens': int(prompt),
        'candidates_tokens': int(candidates),
        'total_tokens': int(getattr(meta, 'total_token_count', prompt + candidates) or (prompt + candidates)),
    }


def _record_usage(usage):
    try:
        from apps.core.models import GeminiUsageTracker
        GeminiUsageTracker.record_usage(
            prompt_tokens=usage.get('prompt_tokens', 0),
            candidates_tokens=usage.get('candidates_tokens', 0),
        )
    except Exception as exc:  # pragma: no cover - tracking must not break chat
        logger.debug('Gemini usage tracking skipped: %s', type(exc).__name__)


def _parse_structured(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        # Models occasionally wrap JSON in a fenced block even with a schema.
        match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except (TypeError, ValueError):
                return None
    return None


def generate(prompt, *, system_instruction=None, images=None, response_schema=None,
             temperature=0.2, max_output_tokens=4096):
    """Generate one AI response with no application-level duplicate retries.

    Bounded retries are delegated to the installed google-genai SDK via
    ``HttpRetryOptions`` for retryable HTTP statuses.  Timeouts and 4xx errors
    fail fast and are classified for friendly fallback handling.
    """
    if not is_ai_configured():
        raise AiNotConfigured()
    if not _daily_budget_remaining():
        raise AiQuotaExceeded()

    client, types = _make_client()
    model = model_name()

    contents = [prompt]
    for image in images or []:
        image_bytes = getattr(image, 'data', None)
        mime_type = getattr(image, 'mime_type', None)
        if image_bytes and mime_type:
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    config_kwargs = {
        'temperature': temperature,
        'max_output_tokens': max_output_tokens,
    }
    if system_instruction:
        config_kwargs['system_instruction'] = system_instruction
    if response_schema:
        config_kwargs['response_mime_type'] = 'application/json'
        config_kwargs['response_schema'] = response_schema
    try:
        config = types.GenerateContentConfig(**config_kwargs)
    except Exception as exc:
        raise AiInvalidRequest('Could not construct the AI request.') from exc

    try:
        response = client.models.generate_content(model=model, contents=contents, config=config)
    except Exception as exc:
        classified = _classify_exception(exc)
        # Log only safe metadata: never prompt text, key material, or raw body.
        logger.warning(
            'Gemini request failed: category=%s status=%s exception=%s',
            classified.category, classified.status_code, type(exc).__name__,
        )
        raise classified from exc

    text = getattr(response, 'text', '') or ''
    parsed = getattr(response, 'parsed', None)
    if parsed is not None and not isinstance(parsed, dict):
        try:
            parsed = dict(parsed)
        except (TypeError, ValueError):
            parsed = None
    if parsed is None and response_schema:
        parsed = _parse_structured(text)

    finish_reason = ''
    candidates = getattr(response, 'candidates', None) or []
    if candidates:
        finish_reason = str(getattr(candidates[0], 'finish_reason', '') or '')

    usage = _extract_usage(response)
    _record_usage(usage)
    return AiResult(
        text=text,
        structured=parsed,
        model=model,
        usage=usage,
        raw_finish_reason=finish_reason,
    )


def fallback_model_name():
    return (getattr(settings, 'GEMINI_FALLBACK_MODEL', '') or '').strip().replace('models/', '')
