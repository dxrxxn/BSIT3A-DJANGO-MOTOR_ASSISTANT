"""Adapter around the verified local repair knowledge base."""
from __future__ import annotations

import re

from apps.motor.knowledge import retrieve_verified_knowledge

SYSTEM_COMPONENT_HINTS = {
    'brake': ['brakes'],
    'brakes': ['brakes'],
    'preno': ['brakes'],
    'starting': ['engine', 'battery', 'sprocket'],
    'electrical': ['battery'],
    'charging': ['battery'],
    'cooling': ['engine'],
    'overheat': ['engine'],
    'exhaust': ['exhaust'],
    'fuel': ['engine'],
    'engine': ['engine'],
    'transmission': ['engine', 'sprocket'],
    'drivetrain': ['sprocket', 'wheels'],
    'suspension': ['suspension'],
    'steering': ['suspension', 'controls'],
    'tire': ['wheels'],
    'tyre': ['wheels'],
    'wheel': ['wheels'],
    'lighting': ['lighting'],
    'body': ['bodywork'],
}


def search_local_knowledge(message, vehicle_profile=None, max_results=3):
    profile = vehicle_profile or {}
    vehicle_type = (profile.get('vehicle_type') or profile.get('type') or 'all').lower()
    if vehicle_type in ('scooter', 'underbone'):
        vehicle_type = 'motorcycle'
    return retrieve_verified_knowledge(
        message,
        vehicle_type=vehicle_type,
        max_results=max_results,
        vehicle_info=profile,
    )


def evidence_sources(results):
    sources = []
    seen = set()
    for result in results or []:
        for guide in result.get('guides', []):
            title = guide.get('source_title') or guide.get('source_reference') or ''
            reference = guide.get('source_reference') or ''
            date = guide.get('source_date') or ''
            key = (title.lower(), reference.lower(), date)
            if not (title or reference) or key in seen:
                continue
            seen.add(key)
            sources.append({
                'title': title,
                'reference': reference,
                'reviewed': bool(guide.get('reviewed')),
                'date': date,
            })
    return sources[:8]


def evidence_prompt(results):
    """Render only the retrieved records, with explicit source attribution."""
    if not results:
        return 'No matching approved local repair record was found.'
    blocks = []
    for result in results:
        blocks.append(
            f"### LOCAL RECORD: {result.get('symptom_name')} "
            f"(system: {result.get('system') or result.get('category')}; vehicle: {result.get('vehicle_type')})"
        )
        if result.get('safety_warning'):
            blocks.append(f"Record safety note: {result['safety_warning']}")
        for guide in result.get('guides', [])[:4]:
            blocks.append(f"- Possible cause: {guide.get('possible_cause')}")
            blocks.append(f"  Confidence: {guide.get('confidence_level')}")
            blocks.append(f"  Diagnostic check: {guide.get('diagnostic_test')}")
            blocks.append(f"  Expected: {guide.get('expected_result')}")
            blocks.append(f"  If abnormal: {guide.get('alternative_outcome')}")
            blocks.append(f"  Tools: {guide.get('tools_required')}")
            blocks.append(f"  Repair steps: {guide.get('repair_instructions')}")
            blocks.append(f"  Verify: {guide.get('verification_procedure')}")
            blocks.append(f"  Stop when: {guide.get('when_to_stop')}")
            blocks.append(f"  Source: {guide.get('source_title') or guide.get('source_reference')}")
            parts = guide.get('required_parts') or []
            if parts:
                blocks.append('  Parts mentioned in the local record: ' + ', '.join(
                    f"{part.get('name')}"
                    + (f" (part number {part.get('part_number')})" if part.get('part_number') else '')
                    for part in parts
                ))
    return '\n'.join(blocks)


def related_components(message, results=None):
    text = (message or '').lower()
    components = []
    for keyword, ids in SYSTEM_COMPONENT_HINTS.items():
        if re.search(r'\b' + re.escape(keyword), text):
            for component in ids:
                if component not in components:
                    components.append(component)
    for result in results or []:
        system = (result.get('system') or result.get('category') or '').lower()
        for keyword, ids in SYSTEM_COMPONENT_HINTS.items():
            if keyword in system:
                for component in ids:
                    if component not in components:
                        components.append(component)
    return components[:8]
