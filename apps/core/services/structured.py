"""Structured diagnostic response schema, validation and safe normalisation.

The model is asked for JSON, but the frontend only receives data that has
passed through this module.  Unknown fields are discarded, list sizes and
string lengths are bounded, and the local safety assessment is always merged
ahead of model-generated warnings.
"""
from __future__ import annotations

import re

from .safety import merge_safety_into_structured

SEVERITIES = {'none', 'caution', 'warning', 'critical'}
CONFIDENCE = {'high', 'medium', 'low', 'tentative', 'possible', 'confirmed'}
STAGES = {
    'general', 'identification', 'symptom', 'safety', 'tests', 'diagnosis',
    'repair', 'verification', 'closed',
}
COMPONENT_IDS = {
    'overview', 'engine', 'brakes', 'exhaust', 'wheels', 'suspension',
    'bodywork', 'controls', 'lighting', 'battery', 'sprocket',
}

REPAIR_STEP_SCHEMA = {
    'type': 'object',
    'properties': {
        'step': {'type': 'integer'},
        'instruction': {'type': 'string'},
        'safety': {'type': 'string'},
    },
    'required': ['instruction'],
}

RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'reply_text': {'type': 'string'},
        'language': {'type': 'string'},
        'intent': {'type': 'string'},
        'diagnostic_stage': {
            'type': 'string',
            'enum': sorted(STAGES),
        },
        'vehicle_profile': {
            'type': 'object',
            'properties': {
                'vehicle_type': {'type': 'string'},
                'make': {'type': 'string'},
                'model': {'type': 'string'},
                'year': {'type': 'string'},
                'variant': {'type': 'string'},
                'engine_displacement': {'type': 'string'},
                'fuel_system': {'type': 'string'},
            },
        },
        'symptoms': {'type': 'array', 'items': {'type': 'string'}},
        'missing_questions': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'question': {'type': 'string'},
                    'why': {'type': 'string'},
                    'options': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['question'],
            },
        },
        'safety': {
            'type': 'object',
            'properties': {
                'severity': {'type': 'string', 'enum': sorted(SEVERITIES)},
                'summary': {'type': 'string'},
                'warnings': {'type': 'array', 'items': {'type': 'string'}},
                'stop_use': {'type': 'boolean'},
            },
        },
        'possible_causes': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'cause': {'type': 'string'},
                    'confidence': {'type': 'string'},
                    'evidence': {'type': 'string'},
                    'uncertainty': {'type': 'string'},
                },
                'required': ['cause'],
            },
        },
        'findings': {'type': 'string'},
        'visible_evidence': {'type': 'array', 'items': {'type': 'string'}},
        'diagnostic_tests': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'purpose': {'type': 'string'},
                    'tools': {'type': 'array', 'items': {'type': 'string'}},
                    'expected': {'type': 'string'},
                    'if_abnormal': {'type': 'string'},
                    'safety': {'type': 'string'},
                },
                'required': ['name'],
            },
        },
        'required_tools': {'type': 'array', 'items': {'type': 'string'}},
        'required_parts': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'part_number': {'type': 'string'},
                    'compatibility_verified': {'type': 'boolean'},
                    'note': {'type': 'string'},
                },
                'required': ['name'],
            },
        },
        'repair_steps': {'type': 'array', 'items': REPAIR_STEP_SCHEMA},
        'verification': {'type': 'array', 'items': {'type': 'string'}},
        'sources': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string'},
                    'reference': {'type': 'string'},
                    'reviewed': {'type': 'boolean'},
                    'date': {'type': 'string'},
                },
                'required': ['title'],
            },
        },
        'next_action': {'type': 'string'},
        'related_components': {'type': 'array', 'items': {'type': 'string'}},
        'limitations': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['reply_text', 'intent', 'diagnostic_stage', 'next_action'],
}


def empty_structured(language='english'):
    return {
        'reply_text': '',
        'language': language,
        'intent': 'general_diagnostic',
        'diagnostic_stage': 'symptom',
        'vehicle_profile': {
            'vehicle_type': '', 'make': '', 'model': '', 'year': '',
            'variant': '', 'engine_displacement': '', 'fuel_system': '',
        },
        'symptoms': [],
        'missing_questions': [],
        'safety': {'severity': 'none', 'summary': '', 'warnings': [], 'stop_use': False},
        'possible_causes': [],
        'findings': '',
        'visible_evidence': [],
        'diagnostic_tests': [],
        'required_tools': [],
        'required_parts': [],
        'repair_steps': [],
        'verification': [],
        'sources': [],
        'next_action': '',
        'related_components': [],
        'limitations': [],
        'offline': False,
        'offline_reason': '',
        'chips': [],
    }


def _text(value, limit=2000):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return ''
    return str(value).strip()[:limit]


def _list(value, limit=12):
    return value if isinstance(value, list) else []


def _bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'true', 'yes', '1'}
    return bool(value)


def _confidence(value):
    lowered = _text(value, 30).lower()
    for candidate in ('confirmed', 'high', 'medium', 'low', 'tentative', 'possible'):
        if candidate in lowered:
            return candidate
    return 'possible'


def _stage(value):
    lowered = _text(value, 40).lower().replace(' ', '_')
    return lowered if lowered in STAGES else 'diagnosis'


def _string_list(value, limit=12, item_limit=500):
    result = []
    for item in _list(value, limit):
        text = _text(item, item_limit)
        if text and text not in result:
            result.append(text)
    return result[:limit]


def normalise_structured(data, *, language='english', safety=None, evidence_sources=None,
                         allowed_parts=None, offline=False):
    """Return a bounded, frontend-safe structured response.

    ``evidence_sources`` is the only allowed source list.  Model-provided
    references that do not appear in the local evidence are discarded so the
    UI cannot present an invented service-manual citation.

    ``allowed_parts`` maps normalised part names to locally retrieved records.
    A model-supplied part number or compatibility claim is never trusted on
    its own: it is only shown when the same part was supplied as evidence.
    """
    base = empty_structured(language)
    if not isinstance(data, dict):
        data = {}

    base['reply_text'] = _text(data.get('reply_text'), 12000)
    base['language'] = _text(data.get('language'), 20).lower() or language
    base['intent'] = _text(data.get('intent'), 80) or 'general_diagnostic'
    base['diagnostic_stage'] = _stage(data.get('diagnostic_stage'))
    base['symptoms'] = _string_list(data.get('symptoms'), limit=10)

    profile = data.get('vehicle_profile') if isinstance(data.get('vehicle_profile'), dict) else {}
    base['vehicle_profile'] = {
        key: _text(profile.get(key), 120)
        for key in ('vehicle_type', 'make', 'model', 'year', 'variant', 'engine_displacement', 'fuel_system')
    }

    for question in _list(data.get('missing_questions'), 5):
        if not isinstance(question, dict):
            continue
        text = _text(question.get('question'), 500)
        if not text:
            continue
        base['missing_questions'].append({
            'question': text,
            'why': _text(question.get('why'), 300),
            'options': _string_list(question.get('options'), limit=8, item_limit=200),
        })

    for cause in _list(data.get('possible_causes'), 8):
        if not isinstance(cause, dict):
            continue
        text = _text(cause.get('cause'), 500)
        if not text:
            continue
        base['possible_causes'].append({
            'cause': text,
            'confidence': _confidence(cause.get('confidence')),
            'evidence': _text(cause.get('evidence'), 700),
            'uncertainty': _text(cause.get('uncertainty'), 500),
        })
    base['findings'] = _text(data.get('findings'), 1500)
    base['visible_evidence'] = _string_list(
        data.get('visible_evidence'), limit=10, item_limit=700,
    )

    for test in _list(data.get('diagnostic_tests'), 10):
        if not isinstance(test, dict):
            continue
        name = _text(test.get('name'), 300)
        if not name:
            continue
        base['diagnostic_tests'].append({
            'name': name,
            'purpose': _text(test.get('purpose'), 700),
            'tools': _string_list(test.get('tools'), limit=8, item_limit=160),
            'expected': _text(test.get('expected'), 700),
            'if_abnormal': _text(test.get('if_abnormal'), 700),
            'safety': _text(test.get('safety'), 700),
        })

    base['required_tools'] = _string_list(data.get('required_tools'), limit=20, item_limit=160)

    allowed_parts = allowed_parts or {}
    for part in _list(data.get('required_parts'), 10):
        if not isinstance(part, dict):
            continue
        name = _text(part.get('name'), 200)
        if not name:
            continue
        stored = allowed_parts.get(name.casefold()) if isinstance(allowed_parts, dict) else None
        if isinstance(stored, dict):
            # The local record is authoritative for both the catalogue number
            # and fitment status.  An AI response can repeat it, but cannot
            # create or upgrade it.
            name = _text(stored.get('name'), 200) or name
            part_number = _text(stored.get('part_number'), 80)
            verified = bool(stored.get('compatibility_verified'))
        else:
            part_number = ''
            verified = False
        base['required_parts'].append({
            'name': name,
            'part_number': part_number,
            'compatibility_verified': verified,
            'note': _text(part.get('note'), 300),
        })

    for index, step in enumerate(_list(data.get('repair_steps'), 24), start=1):
        if isinstance(step, str):
            instruction = _text(step, 1200)
            safety_text = ''
        elif isinstance(step, dict):
            instruction = _text(step.get('instruction'), 1200)
            safety_text = _text(step.get('safety'), 500)
        else:
            continue
        if not instruction:
            continue
        base['repair_steps'].append({
            'step': index,
            'instruction': instruction,
            'safety': safety_text,
        })

    base['verification'] = _string_list(data.get('verification'), limit=12, item_limit=700)
    base['next_action'] = _text(data.get('next_action'), 1200)
    base['limitations'] = _string_list(data.get('limitations'), limit=8, item_limit=500)
    base['offline'] = bool(offline)

    allowed = []
    for source in evidence_sources or []:
        if not isinstance(source, dict):
            continue
        title = _text(source.get('title') or source.get('source_title'), 255)
        reference = _text(source.get('reference') or source.get('source_reference'), 500)
        if not title and not reference:
            continue
        allowed.append({
            'title': title or reference,
            'reference': reference,
            'reviewed': bool(source.get('reviewed', True)),
            'date': _text(source.get('date') or source.get('source_date'), 40),
        })

    # Only local evidence references are shown.  This is intentionally strict:
    # a plausible-looking manual citation must not be displayed unless it came
    # from the reviewed local knowledge base.
    if allowed:
        base['sources'] = allowed[:8]
    else:
        base['sources'] = []

    components = []
    for component in _string_list(data.get('related_components'), limit=8, item_limit=40):
        component = component.lower()
        if component in COMPONENT_IDS and component not in components:
            components.append(component)
    base['related_components'] = components

    if safety is not None:
        base = merge_safety_into_structured(base, safety)

    # Remove raw model markup that the UI does not render here.
    base['reply_text'] = re.sub(r'\[(?:part-image|vehicle-form):[^\]]*\]', '', base['reply_text']).strip()
    return base


def validate_structured(structured):
    """Return (is_valid, list_of_errors)."""
    errors = []
    if not isinstance(structured, dict):
        return False, ['response is not an object']
    if not structured.get('reply_text') and not structured.get('missing_questions') and not structured.get('possible_causes'):
        errors.append('response has no usable answer')
    if structured.get('safety', {}).get('severity') not in SEVERITIES:
        errors.append('invalid safety severity')
    if structured.get('diagnostic_stage') not in STAGES:
        errors.append('invalid diagnostic stage')
    for key in ('missing_questions', 'possible_causes', 'diagnostic_tests', 'repair_steps', 'sources'):
        if not isinstance(structured.get(key), list):
            errors.append(f'{key} is not a list')
    return not errors, errors


def fallback_needed(structured):
    valid, _ = validate_structured(structured)
    return not valid
