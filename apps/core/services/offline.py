"""Offline, evidence-backed diagnostic answers.

When Gemini is unavailable, this module builds a clearly labelled answer from
approved local records.  It never claims that Gemini generated the response,
and it does not invent torque values, part compatibility, or service limits.
"""
from __future__ import annotations

import re

from .intake import (
    NO_START_OPTIONS,
    classify_no_start,
    is_no_start_topic,
    missing_symptom_questions,
    missing_vehicle_questions,
    next_step_hint,
    vehicle_label,
)
from .knowledge import evidence_sources, related_components
from .structured import empty_structured

LABELS = {
    'english': {
        'offline': 'Offline knowledge — this answer comes from the local reviewed repair library. Gemini was not used.',
        'vehicle': 'Vehicle and problem',
        'safety': 'Safety first',
        'questions': 'What I still need to know',
        'causes': 'What this could indicate',
        'tests': 'Safe checks, in order',
        'tools': 'Tools and parts',
        'steps': 'Repair guidance from the record',
        'verification': 'How to verify',
        'sources': 'Sources in the local library',
        'next': 'Next action',
        'limitations': 'Limitations',
        'no_record': 'No approved local repair record matched this question closely enough. I will not guess at a repair procedure or specification.',
        'checks_first': 'Complete the checks before replacing parts. The steps below are from the stored record and may not match your exact variant.',
        'source_language': 'Technical procedure text is kept close to its source wording to avoid changing measurements or safety meaning.',
        'confidence': 'Confidence',
        'expected': 'Expected',
        'if_abnormal': 'If abnormal',
    },
    'tagalog': {
        'offline': 'Offline kaalaman — galing sa lokal na reviewed repair library ang sagot na ito. Hindi ginamit ang Gemini.',
        'vehicle': 'Sasakyan at problema',
        'safety': 'Kaligtasan muna',
        'questions': 'Kailangan ko pang malaman',
        'causes': 'Maaaring dahilan',
        'tests': 'Ligtas na pagsusuri, sunod-sunod',
        'tools': 'Gamit at piyesa',
        'steps': 'Gabay sa pag-aayos mula sa record',
        'verification': 'Paano i-verify',
        'sources': 'Pinagkunan sa lokal na library',
        'next': 'Susunod na hakbang',
        'limitations': 'Limitasyon',
        'no_record': 'Walang sapat na tugmang approved local repair record. Hindi ako maghuhula ng procedure o specification.',
        'checks_first': 'Tapusin muna ang checks bago magpalit ng piyesa. Ang mga hakbang sa ibaba ay mula sa naka-store na record at maaaring hindi eksakto sa variant mo.',
        'source_language': 'Ang teknikal na procedure ay pinananatili malapit sa orihinal na salita upang hindi mabago ang sukat o kahulugan ng safety.',
        'confidence': 'Kumpiyansa',
        'expected': 'Inaasahan',
        'if_abnormal': 'Kung abnormal',
    },
    'hiligaynon': {
        'offline': 'Offline kaalaman — gikan sa lokal nga reviewed repair library ang sabat. Wala ginamit ang Gemini.',
        'vehicle': 'Salakyan kag problema',
        'safety': 'Kaligtasan anay',
        'questions': 'Kinahanglan ko pa mahibaluan',
        'causes': 'Mahimo nga kabangdanan',
        'tests': 'Hilway nga pagsusi, sunod-sunod',
        'tools': 'Gamit kag parte',
        'steps': 'Giya sa pagkay-o halin sa record',
        'verification': 'Paano i-verify',
        'sources': 'Ginakuhaan sa lokal nga library',
        'next': 'Sunod nga tikang',
        'limitations': 'Limitasyon',
        'no_record': 'Wala sang husto nga approved local repair record. Indi ako magguwa-guwa sang procedure ukon specification.',
        'checks_first': 'Tapusa anay ang checks antes mag-ilis sang parte. Ang mga tikang sa idalom halin sa naka-store nga record kag mahimo indi eksakto sa imo variant.',
        'source_language': 'Ang teknikal nga procedure ginapabilin malapit sa orihinal nga hambal agud indi magbaylo ang sukod ukon kahulugan sang kaligtasan.',
        'confidence': 'Kasiguruhan',
        'expected': 'Ginalauman',
        'if_abnormal': 'Kon abnormal',
    },
}


def _label(language, key):
    return LABELS.get(language, LABELS['english']).get(key, LABELS['english'].get(key, key))


def _split_steps(text):
    steps = []
    for line in (text or '').splitlines():
        cleaned = re.sub(r'^\s*(?:[-*]\s*)?(?:\[\s*\]\s*)?(?:\d+[\.\):\-]\s*)?', '', line).strip()
        if cleaned:
            steps.append(cleaned)
    return steps


def _split_tools(text):
    pieces = re.split(r'[,\n;•]+', text or '')
    return [piece.strip() for piece in pieces if piece.strip()][:20]


def _source_list(evidence):
    return evidence_sources(evidence)


def _compose_reply(structured, language):
    labels = LABELS.get(language, LABELS['english'])
    lines = []
    vehicle = ' '.join(filter(None, [
        structured['vehicle_profile'].get('year'),
        structured['vehicle_profile'].get('make'),
        structured['vehicle_profile'].get('model'),
        structured['vehicle_profile'].get('variant'),
    ])).strip()
    if vehicle:
        lines.append(f"**{labels['vehicle']}:** {vehicle}")
    if structured.get('symptoms'):
        lines.append(f"**Symptom:** {'; '.join(structured['symptoms'][:3])}")
    lines.append(f"> [!NOTE]\n> {labels['offline']}")
    if structured['safety'].get('warnings'):
        lines.append(f"**{labels['safety']}:**")
        lines.extend(f"> {warning}" for warning in structured['safety']['warnings'])
    if structured.get('missing_questions'):
        lines.append(f"**{labels['questions']}:**")
        for question in structured['missing_questions']:
            lines.append(f"- {question['question']}")
            for option in question.get('options', []):
                lines.append(f"  - {option}")
    if structured.get('possible_causes'):
        lines.append(f"**{labels['causes']}:**")
        for cause in structured['possible_causes'][:5]:
            suffix = f" — {labels['confidence']}: {cause['confidence']}"
            lines.append(f"- {cause['cause']}{suffix}")
            if cause.get('evidence'):
                lines.append(f"  - {cause['evidence']}")
            if cause.get('uncertainty'):
                lines.append(f"  - {cause['uncertainty']}")
    if structured.get('diagnostic_tests'):
        lines.append(f"**{labels['tests']}:**")
        for test in structured['diagnostic_tests'][:5]:
            lines.append(f"- {test['name']}")
            if test.get('expected'):
                lines.append(f"  - {labels['expected']}: {test['expected']}")
            if test.get('if_abnormal'):
                lines.append(f"  - {labels['if_abnormal']}: {test['if_abnormal']}")
            if test.get('safety'):
                lines.append(f"  - {labels['safety']}: {test['safety']}")
    if structured.get('required_tools'):
        lines.append(f"**{labels['tools']}:**")
        lines.extend(f"- {tool}" for tool in structured['required_tools'][:12])
    if structured.get('required_parts'):
        lines.append(f"**Parts:**")
        for part in structured['required_parts'][:10]:
            verified = 'verified compatibility' if part.get('compatibility_verified') else 'compatibility NOT verified'
            number = f" [{part['part_number']}]" if part.get('part_number') else ''
            lines.append(f"- {part['name']}{number} — {verified}")
    if structured.get('repair_steps'):
        lines.append(f"**{labels['steps']}:**")
        lines.append(f"_{labels['checks_first']}_")
        for step in structured['repair_steps'][:20]:
            lines.append(f"- [ ] {step['step']}. {step['instruction']}")
            if step.get('safety'):
                lines.append(f"  - {labels['safety']}: {step['safety']}")
    if structured.get('verification'):
        lines.append(f"**{labels['verification']}:**")
        lines.extend(f"- {item}" for item in structured['verification'][:8])
    if structured.get('sources'):
        lines.append(f"**{labels['sources']}:**")
        for source in structured['sources'][:6]:
            reviewed = 'reviewed' if source.get('reviewed') else 'unreviewed'
            date = f" ({source['date']})" if source.get('date') else ''
            lines.append(f"- {source.get('title') or source.get('reference')}{date} — {reviewed}")
        lines.append(f"_{labels['source_language']}_")
    if structured.get('limitations'):
        lines.append(f"**{labels['limitations']}:**")
        lines.extend(f"- {item}" for item in structured['limitations'][:6])
    if structured.get('next_action'):
        lines.append(f"**{labels['next']}:** {structured['next_action']}")

    chips = []
    for question in structured.get('missing_questions', []):
        for option in question.get('options', [])[:5]:
            label = re.sub(r'^[A-E][\.\)]\s*', '', option).strip()
            if label:
                chips.append(label)
    if chips:
        lines.append(f"[chips: {' | '.join(chips[:5])}]")
    return '\n\n'.join(lines)


def build_offline_response(message, conversation, profile, evidence, safety,
                           language='english', experience_level='beginner'):
    structured = empty_structured(language)
    structured['offline'] = True
    structured['language'] = language
    structured['intent'] = 'diagnostic_offline'
    structured['vehicle_profile'] = {
        'vehicle_type': profile.get('vehicle_type') or '',
        'make': profile.get('make') or '',
        'model': profile.get('model') or '',
        'year': profile.get('year') or '',
        'variant': profile.get('variant') or '',
        'engine_displacement': profile.get('engine_displacement') or '',
        'fuel_system': profile.get('fuel_system') or '',
    }
    structured['symptoms'] = [message.strip()[:500]] if message.strip() else []
    structured['related_components'] = related_components(message, evidence)

    missing = missing_vehicle_questions(
        profile, language=language,
        asked_questions=conversation.asked_questions if conversation else [],
    )
    if not missing:
        missing = missing_symptom_questions(
            message, language=language,
            asked_questions=conversation.asked_questions if conversation else [],
        )
    structured['missing_questions'] = missing[:2]

    subtype = classify_no_start(message) if is_no_start_topic(message) else None
    if not evidence:
        structured['limitations'] = [
            LABELS.get(language, LABELS['english'])['no_record'],
        ]
        hint = next_step_hint(subtype, language=language) if subtype else ''
        if hint:
            structured['next_action'] = hint
        elif missing:
            structured['next_action'] = missing[0]['question']
        else:
            structured['next_action'] = {
                'english': 'Tell me when the symptom happens, whether it changes with temperature or load, and any recent repair or fluid change.',
                'tagalog': 'Sabihin kung kailan nangyayari ang sintomas, kung nagbabago ito sa temperatura o load, at anumang bagong repair o fluid change.',
                'hiligaynon': 'Hambala kon san-o nagakatabo ang sintomas, kon nagabaylo ini sa temperatura ukon load, kag bisan ano nga bag-o nga repair ukon fluid change.',
            }[language]
        structured['reply_text'] = _compose_reply(structured, language)
        return structured

    # Build from the best approved records.
    causes = []
    tests = []
    tools = []
    parts = []
    steps = []
    verification = []
    seen_causes = set()
    seen_tests = set()
    seen_steps = set()
    for result in evidence[:3]:
        for guide in result.get('guides', [])[:3]:
            cause = (guide.get('possible_cause') or '').strip()
            if cause and cause.lower() not in seen_causes:
                seen_causes.add(cause.lower())
                causes.append({
                    'cause': cause,
                    'confidence': (guide.get('confidence_level') or 'possible').lower(),
                    'evidence': guide.get('diagnostic_test') or '',
                    'uncertainty': guide.get('alternative_outcome') or '',
                })
            test_name = (guide.get('diagnostic_test') or '').strip()
            if test_name and test_name.lower() not in seen_tests:
                seen_tests.add(test_name.lower())
                tests.append({
                    'name': test_name,
                    'purpose': cause,
                    'tools': _split_tools(guide.get('tools_required') or ''),
                    'expected': guide.get('expected_result') or '',
                    'if_abnormal': guide.get('alternative_outcome') or '',
                    'safety': guide.get('safety_precautions') or result.get('safety_warning') or '',
                })
            for tool in _split_tools(guide.get('tools_required') or ''):
                if tool not in tools:
                    tools.append(tool)
            for part in guide.get('required_parts') or []:
                name = part.get('name') if isinstance(part, dict) else str(part)
                if name and not any(existing.get('name') == name for existing in parts):
                    if isinstance(part, dict):
                        parts.append({
                            'name': name,
                            'part_number': part.get('part_number') or '',
                            'compatibility_verified': False,
                            'note': 'Compatibility is not verified from this local record.',
                        })
                    else:
                        parts.append({
                            'name': name, 'part_number': '',
                            'compatibility_verified': False,
                            'note': 'Compatibility not verified.',
                        })
            for step in _split_steps(guide.get('repair_instructions') or ''):
                key = step.lower()
                if key not in seen_steps:
                    seen_steps.add(key)
                    steps.append(step)
            verify = (guide.get('verification_procedure') or guide.get('expected_result') or '').strip()
            if verify and verify not in verification:
                verification.append(verify)
            if guide.get('when_to_stop'):
                stop = f"Stop and seek professional help: {guide['when_to_stop']}"
                if stop not in verification:
                    verification.append(stop)

    structured['possible_causes'] = causes[:8]
    structured['diagnostic_tests'] = tests[:8]
    structured['required_tools'] = tools[:20]
    structured['required_parts'] = parts[:10]
    structured['repair_steps'] = [
        {'step': index, 'instruction': instruction, 'safety': ''}
        for index, instruction in enumerate(steps[:20], start=1)
    ]
    structured['verification'] = verification[:10]
    structured['sources'] = _source_list(evidence)

    if missing:
        structured['diagnostic_stage'] = 'tests' if structured['diagnostic_tests'] else 'symptom'
        structured['next_action'] = missing[0]['question']
    else:
        structured['diagnostic_stage'] = 'repair' if structured['repair_steps'] else 'diagnosis'
        structured['next_action'] = (
            structured['diagnostic_tests'][0]['name']
            if structured['diagnostic_tests']
            else 'Record what you find, then ask for the next check.'
        )
        if structured['diagnostic_tests']:
            structured['next_action'] = (
                'Start with the first safe check: ' + structured['diagnostic_tests'][0]['name']
            )
    structured['limitations'] = [
        'This is offline guidance from stored records, not a confirmed diagnosis.',
        'The stored record may not cover your exact model, year, or variant. Verify part numbers and specifications against the manufacturer information for your vehicle.',
    ]
    structured['reply_text'] = _compose_reply(structured, language)
    return structured
