"""Typical motorcycle component locations for offline answers.

These are general layouts, not model-specific service data. Every answer that
uses them must tell the rider to confirm the exact location in the owner's
manual.
"""
from __future__ import annotations

import re


LOCATION_HINTS = (
    (
        r'\boil\s+filter\b',
        'The oil filter is usually on the side or bottom of the engine '
        'crankcase, behind a circular cover or as an external spin-on canister.',
    ),
    (
        r'\bair\s+filter\b',
        'The air filter is inside the airbox, usually under the seat or behind '
        'a side panel.',
    ),
    (
        r'\bbattery\b|\bbaterya\b',
        'The battery is usually under the seat, behind a side panel, or under '
        'the front fairing on some scooters.',
    ),
    (
        r'\bspark\s+plug\b',
        'The spark plug is at the top or center of the cylinder head, sometimes '
        'under the fuel tank or a small access cover.',
    ),
    (
        r'\bfuse\b|\bfuse\s+box\b',
        'The main fuse/fuse box is usually near the battery, under the seat, or '
        'behind a side cover.',
    ),
    (
        r'\becu\b|\becm\b|\bcdi\b|\btci\b',
        'The ECU/CDI is usually under the seat, near the battery, behind a side '
        'panel, or under the front fairing; it varies widely by model.',
    ),
    (
        r'\bhorn\b',
        'The horn is usually near the front fork, behind the front panel, or '
        'close to the headlight.',
    ),
    (
        r'\bstarter\s+relay\b|\bsolenoid\b',
        'The starter relay/solenoid is usually near the battery, under the seat '
        'or behind a side cover.',
    ),
    (
        r'\bfuel\s+pump\b',
        'The fuel pump is inside the fuel tank on EFI bikes, or near the tank on '
        'carbureted bikes.',
    ),
    (
        r'\bfuel\s+filter\b',
        'The fuel filter is usually inline under the fuel tank or near the fuel '
        'pump; some models use a strainer inside the tank.',
    ),
    (
        r'\bregulator\b|\brectifier\b',
        'The regulator/rectifier is usually behind a front panel or near the '
        'battery.',
    ),
    (
        r'\bchain\b|\bkadena\b',
        'The chain runs along the left side of the rear wheel and swingarm.',
    ),
    (
        r'\bbrake\s+fluid\s+reservoir\b|\bmaster\s+cylinder\b',
        'The brake fluid reservoir/master cylinder is usually at the handlebar '
        'for the front brake, or near the rear brake pedal on models with a '
        'separate rear reservoir.',
    ),
    (
        r'\bbrake\b|\bcaliper\b|\bpads?\b',
        'The brake pads/caliper are at the wheel, on the front fork or rear '
        'swingarm.',
    ),
    (
        r'\bcvt\b|\bbelt\b|\bvariator\b',
        'The CVT is the large casing on the left side of the rear wheel on '
        'scooters.',
    ),
    (
        r'\bradiator\s+cap\b',
        'The radiator cap is usually on top of the radiator, often behind the '
        'front panel or under the fuel tank.',
    ),
    (
        r'\bcoolant\b|\bradiator\b|\breservoir\b',
        'The coolant reservoir is usually behind the front panel or near the '
        'engine.',
    ),
    (
        r'\bthrottle\s+body\b|\binjector\b',
        'The throttle body/injector is under the seat/airbox, on the intake side '
        'of the engine.',
    ),
    (
        r'\bheadlight\b|\bbulb\b',
        'The headlight bulb is inside the headlight housing, behind the rear '
        'connector.',
    ),
    (
        r'\btail\s?light\b',
        'The tail light is on the rear fender or body panel.',
    ),
    (
        r'\bsidestand\b|\bkickstand\b',
        'The sidestand switch is at the sidestand pivot.',
    ),
    (
        r'\bclutch\b',
        'The clutch is on the right side of the engine on manual bikes; scooters '
        'use a CVT instead.',
    ),
)


def location_hint(message):
    """Return the typical location text for a named part, or an empty string."""
    msg = (message or '').lower()
    for pattern, hint in LOCATION_HINTS:
        if re.search(pattern, msg):
            return hint
    return ''
