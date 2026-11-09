"""Online verification layer for MotorAssistant / J.A.R.V.I.S.

Verifies technical claims (specifications, intervals, fluid types, torque values,
part numbers, and safety claims) when an AI/web provider is configured.
When unavailable, strictly marks answers as unverified_offline with appropriate
disclosures. Never invents sources, URLs, page numbers, or values.
"""
from __future__ import annotations

import logging
from django.conf import settings
from django.utils import timezone

from .ai import is_ai_available, generate

logger = logging.getLogger(__name__)

VERIFIABLE_INTENTS = {
    'spec',
    'maintenance_howto',
    'safety',
}

VERIFIABLE_CATEGORIES = [
    'specification',
    'interval',
    'fluid_type',
    'torque_value',
    'part_number',
    'safety_claim',
]


def needs_verification(intent: str, question: str) -> bool:
    """True if the query involves technical specs, intervals, fluids, torque, or safety."""
    if intent in VERIFIABLE_INTENTS:
        return True
    q = (question or '').lower()
    return any(term in q for term in [
        'valve clearance', 'spark plug gap', 'coolant', 'cvt belt', 'roller',
        'torque', 'spec', 'pressure', 'gap', 'clearance', 'interval', 'how often',
        'what oil', 'oil type', 'clutch cable', 'charging voltage', 'part number',
    ])


def verify_technical_claim(
    question: str,
    proposed_answer: str,
    vehicle_profile: dict | None = None,
    intent: str | None = None,
    language: str = 'english',
) -> dict:
    """Verify technical claims against authoritative sources when AI provider is active.

    Returns:
      {
        'verification_status': 'verified' | 'unverified_offline',
        'source_title': str,
        'reference': str,
        'retrieval_time': str,
        'applicability': str,
        'confidence': float,
        'verified_claim': str,
        'disclosure': str,
      }
    """
    now_iso = timezone.now().isoformat()
    veh_profile = vehicle_profile or {}
    make = veh_profile.get('make') or ''
    model = veh_profile.get('model') or ''
    year = veh_profile.get('year') or 'unknown'
    applicability = f"{year} {make} {model}".strip() or "general motorcycle"

    offline_disclosure = {
        'english': (
            "Technical guidance disclosure: This is unverified offline guidance from local records. "
            "Always verify specifications, torque values, and service intervals against the official "
            "OEM service manual before performing repairs."
        ),
        'tagalog': (
            "Paalala sa teknikal na detalye: Ito ay hindi beripikadong offline na gabay mula sa lokal na talaan. "
            "Laging tiyakin ang mga sukat, torque, at schedule sa opisyal na service manual ng manufacturer bago mag-ayos."
        ),
        'hiligaynon': (
            "Pahibalo sa teknikal nga giya: Ini indi beripikado nga offline nga sabat halin sa lokal nga library. "
            "Siguraduha gid ang mga sukod kag schedule sa opisyal nga service manual sang salakyan antes magkay-o."
        ),
    }.get(language, {
        'english': "Unverified offline guidance. Confirm with official OEM service manual."
    }['english'])

    # If provider is not available/configured, return unverified_offline
    if not is_ai_available() or not getattr(settings, 'GEMINI_API_KEY', ''):
        return {
            'verification_status': 'unverified_offline',
            'source_title': '',
            'reference': '',
            'retrieval_time': now_iso,
            'applicability': applicability,
            'confidence': 0.0,
            'verified_claim': '',
            'disclosure': offline_disclosure,
        }

    # Only verify technical/safety claims
    if not needs_verification(intent or '', question):
        return {
            'verification_status': 'unverified_offline',
            'source_title': '',
            'reference': '',
            'retrieval_time': now_iso,
            'applicability': applicability,
            'confidence': 0.0,
            'verified_claim': '',
            'disclosure': '',
        }

    # Live verification via provider
    prompt = f"""You are a technical fact-checker for motorcycle service manuals.
Verify the technical specification, interval, fluid type, torque value, or part in this answer:

QUESTION: {question}
VEHICLE APPLICABILITY: {applicability}
PROPOSED ANSWER: {proposed_answer}

RULES:
1. State whether the technical value or procedure matches authoritative OEM service data.
2. If verified, cite the exact OEM manual or authoritative service reference.
3. NEVER invent a source, URL, manual, page number, or value. If not authoritative, state unverified.
4. Return a compact JSON format with:
   {{"verified": true/false, "source_title": "...", "reference": "...", "confidence": 0.0-1.0, "verified_claim": "..."}}
"""
    try:
        res = generate(
            prompt,
            system_instruction="Strict motorcycle technical verification. Return valid JSON only.",
            temperature=0.0,
            max_output_tokens=512,
        )
        import json
        data = json.loads(res.text.strip())
        if data.get('verified') and data.get('source_title'):
            return {
                'verification_status': 'verified',
                'source_title': data.get('source_title', ''),
                'reference': data.get('reference', ''),
                'retrieval_time': now_iso,
                'applicability': applicability,
                'confidence': float(data.get('confidence', 0.9)),
                'verified_claim': data.get('verified_claim', ''),
                'disclosure': f"Verified against: {data.get('source_title')}",
            }
    except Exception as exc:
        logger.info('Live verification failed (%s); marking unverified_offline', type(exc).__name__)

    return {
        'verification_status': 'unverified_offline',
        'source_title': '',
        'reference': '',
        'retrieval_time': now_iso,
        'applicability': applicability,
        'confidence': 0.0,
        'verified_claim': '',
        'disclosure': offline_disclosure,
    }
