"""Server-side conversation memory.

Client-supplied history is used only for display/legacy compatibility.  The
structured assistant builds its memory from database rows owned by the
authenticated user.  A conversation ID belonging to another account is never
loaded; a fresh conversation is created instead.
"""
from __future__ import annotations

import re

from django.conf import settings
from django.db import transaction

from apps.core.models import ChatTurn, Conversation

MAX_SUMMARY_CHARS = 6000


def get_or_create_conversation(user, conversation_id=None, *, create=True, language='auto'):
    conversation = None
    if conversation_id:
        try:
            conversation = Conversation.objects.filter(pk=conversation_id, user=user).first()
        except (TypeError, ValueError):
            conversation = None
    if conversation is None:
        conversation = (
            Conversation.objects.filter(user=user, is_active=True)
            .order_by('-updated_at')
            .first()
        )
    if conversation is None and create:
        conversation = Conversation.objects.create(user=user, language=language or 'auto')
    return conversation


def close_conversation(user, conversation_id=None):
    qs = Conversation.objects.filter(user=user, is_active=True)
    if conversation_id:
        qs = qs.filter(pk=conversation_id)
    qs.update(is_active=False, stage='closed')


def person_turns(conversation, limit=None):
    limit = limit or int(getattr(settings, 'ASSISTANT_MAX_CONTEXT_TURNS', 12))
    turns = list(conversation.turns.order_by('-id')[:limit])
    return list(reversed(turns))


def prompt_context(conversation):
    """Compact context for the model, using summary + recent turns only."""
    limit = int(getattr(settings, 'ASSISTANT_MAX_CONTEXT_TURNS', 12))
    turns = person_turns(conversation, limit=limit)
    lines = []
    if conversation.summary:
        lines.append('SUMMARY OF EARLIER CONVERSATION:')
        lines.append(conversation.summary)
        lines.append('')
    lines.append('RECENT CONVERSATION TURNS:')
    if not turns:
        lines.append('(none yet)')
    for turn in turns:
        role = 'User' if turn.role == 'user' else 'Assistant'
        content = (turn.content or '').strip()
        # Avoid sending large JSON/HTML back; the structured answer summary is
        # enough for memory and uses fewer tokens.
        content = re.sub(r'\[(?:chips|part-image|vehicle-form):[^\]]*\]', '', content)
        content = re.sub(r'\s+', ' ', content).strip()[:1200]
        if content:
            lines.append(f'{role}: {content}')
    lines.append('')
    lines.append(f'KNOWN VEHICLE: {conversation.vehicle_profile}')
    if conversation.symptoms:
        lines.append(f'SYMPTOMS REPORTED: {conversation.symptoms}')
    if conversation.asked_questions:
        lines.append('QUESTIONS ALREADY ASKED (do not repeat unless the user asks):')
        lines.extend(f'- {question}' for question in conversation.asked_questions[-10:])
    if conversation.tests_attempted:
        lines.append('TESTS ALREADY ATTEMPTED / ANSWERED:')
        lines.extend(f'- {test}' for test in conversation.tests_attempted[-10:])
    if conversation.findings:
        lines.append(f'FINDINGS SO FAR: {conversation.findings}')
    return '\n'.join(lines)


def _trim(text, limit=MAX_SUMMARY_CHARS):
    text = (text or '').strip()
    return text[-limit:]


def refresh_summary(conversation):
    """Build a deterministic summary without an extra AI request."""
    vehicle = conversation.vehicle_profile
    vehicle_label = ' '.join(filter(None, [
        vehicle.get('year'), vehicle.get('make'), vehicle.get('model'), vehicle.get('variant'),
    ])).strip()
    parts = []
    if vehicle_label:
        parts.append(f'Vehicle: {vehicle_label}.')
    if conversation.symptoms:
        parts.append(f'Reported symptoms: {conversation.symptoms}.')
    if conversation.findings:
        parts.append(f'Findings: {conversation.findings}.')
    if conversation.tests_attempted:
        parts.append('Tests/answers: ' + '; '.join(conversation.tests_attempted[-6:]) + '.')
    if conversation.asked_questions:
        parts.append('Questions asked: ' + '; '.join(conversation.asked_questions[-6:]) + '.')
    turns = person_turns(conversation, limit=6)
    recent = []
    for turn in turns:
        text = re.sub(r'\s+', ' ', turn.content or '').strip()
        if text:
            recent.append(f"{turn.role}: {text[:300]}")
    if recent:
        parts.append('Recent: ' + ' | '.join(recent))
    conversation.summary = _trim(' '.join(parts))
    return conversation.summary


def update_vehicle_from_profile(conversation, profile):
    profile = profile or {}
    mapping = {
        'vehicle_type': 'vehicle_type',
        'make': 'vehicle_make',
        'model': 'vehicle_model',
        'year': 'vehicle_year',
        'variant': 'vehicle_variant',
        'engine_displacement': 'engine_displacement',
        'fuel_system': 'fuel_system',
    }
    changed = False
    for source, target in mapping.items():
        value = str(profile.get(source) or '').strip()
        if value and value.lower() not in {'unknown', 'not sure', 'none'}:
            if getattr(conversation, target) != value:
                setattr(conversation, target, value[:120])
                changed = True
    return changed


def update_conversation_from_structured(conversation, structured, user_message=''):
    """Merge a validated assistant answer into durable diagnostic memory."""
    structured = structured or {}
    is_general = structured.get('diagnostic_stage') == 'general'
    profile = structured.get('vehicle_profile') or {}
    if not profile.get('vehicle_type') and conversation.vehicle_type:
        profile['vehicle_type'] = conversation.vehicle_type
    update_vehicle_from_profile(conversation, profile)

    symptoms = structured.get('symptoms') or []
    existing = (conversation.symptoms or '').strip()
    symptom_set = [item.strip() for item in existing.split(';') if item.strip()]
    lowered = {item.lower() for item in symptom_set}
    for symptom in symptoms:
        text = str(symptom).strip()[:500]
        if text and text.lower() not in lowered:
            symptom_set.append(text)
            lowered.add(text.lower())
    if user_message and not is_general and len(user_message) <= 600:
        if not symptom_set:
            symptom_set.append(user_message.strip())
    conversation.symptoms = '; '.join(symptom_set[-12:])

    missing = [item.get('question', '') for item in structured.get('missing_questions', [])]
    conversation.add_asked_questions(missing)

    tests = [
        item.get('name', '') for item in structured.get('diagnostic_tests', [])
        if isinstance(item, dict)
    ]
    # Suggested tests are not automatically "attempted".  The assistant
    # service adds a test only when the user says they performed it.
    if tests and re.search(r'\b(?:checked|tested|tried|measured|completed|passed|normal|good|ok)\b', user_message or '', re.IGNORECASE):
        conversation.add_tests(tests[:3])

    findings = str(structured.get('findings') or '').strip()
    if findings:
        existing_findings = (conversation.findings or '').strip()
        conversation.findings = (existing_findings + '\n' + findings).strip()[-3000:]

    if not is_general:
        stage = structured.get('diagnostic_stage') or 'diagnosing'
        stage_map = {
            'identification': 'identifying_vehicle',
            'symptom': 'understanding_symptom',
            'safety': 'safety_check',
            'tests': 'diagnosing',
            'diagnosis': 'diagnosing',
            'repair': 'repair_guidance',
            'verification': 'verification',
            'closed': 'closed',
        }
        conversation.stage = stage_map.get(stage, 'diagnosing')

    if not conversation.title:
        if is_general:
            conversation.title = (user_message.strip()[:80] or 'Motorcycle Q&A')
        else:
            vehicle = conversation.vehicle_profile
            label = ' '.join(filter(None, [vehicle.get('make'), vehicle.get('model')])).strip()
            title = (label + ' — ' + (conversation.symptoms or 'Diagnostic session')).strip(' —')
            conversation.title = title[:160]
    refresh_summary(conversation)


@transaction.atomic
def add_turns(conversation, user_message, assistant_message, *, structured=None,
              language='english', mode='ai', safety_severity=''):
    user_turn = ChatTurn.objects.create(
        conversation=conversation,
        user=conversation.user,
        role='user',
        content=user_message,
        language=language,
        mode=mode,
        safety_severity=safety_severity,
    )
    assistant_turn = ChatTurn.objects.create(
        conversation=conversation,
        user=conversation.user,
        role='assistant',
        content=assistant_message,
        language=language,
        structured=structured,
        mode=mode,
        safety_severity=safety_severity,
    )
    return user_turn, assistant_turn
