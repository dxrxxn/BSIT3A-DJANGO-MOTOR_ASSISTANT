"""Input moderation shared by the chat views and assistant services."""
from __future__ import annotations

import re


_PROFANITY_PATTERNS = (
    re.compile(r'\bfuck(?:er|ers|ing|ed|s)?\b', re.IGNORECASE),
    re.compile(r'\bshit(?:ty|ting|s)?\b', re.IGNORECASE),
    re.compile(r'\bbitch(?:es|y)?\b', re.IGNORECASE),
    re.compile(r'\bassholes?\b|\bbastards?\b|\bcunts?\b', re.IGNORECASE),
    re.compile(r'\bdamn(?:ed|ing)?\b', re.IGNORECASE),
    re.compile(
        r'\b(?:putang[\s-]*ina|tang[\s-]*ina|pakyu|pucha|punyeta|pakshet|'
        r'bwisit|leche|gago|gaga|ulol|bobo|tanga|yawa|piste|pisti)\b',
        re.IGNORECASE,
    ),
)

_PROFANITY_WARNINGS = {
    'english': (
        'Please keep the conversation respectful and focused on motorcycles. '
        'Tell me the motorcycle issue or maintenance/parts question you need help with.'
    ),
    'tagalog': (
        'Pakiusap, panatilihing magalang at nakatuon sa motorsiklo ang usapan. '
        'Sabihin ang problema o tanong mo tungkol sa maintenance o piyesa.'
    ),
    'hiligaynon': (
        'Palihog, magpabilin nga matinahuron kag nakapokus sa motorsiklo ang estorya. '
        'Isugid ang problema ukon pamangkot mo parte sa maintenance ukon piyesa.'
    ),
}

_PROFANITY_CHIPS = {
    'english': 'Describe motorcycle issue | Ask about maintenance | Ask about a part',
    'tagalog': 'Ilarawan ang problema ng motor | Magtanong tungkol sa maintenance | Magtanong tungkol sa piyesa',
    'hiligaynon': 'Isugid ang problema sang motor | Pamangkot parte sa maintenance | Pamangkot parte sa piyesa',
}


def profanity_chips(language='english') -> list[str]:
    """Return localized chip labels for the moderation reply."""
    language = language if language in _PROFANITY_CHIPS else 'english'
    return _PROFANITY_CHIPS[language].split(' | ')


def contains_profanity(message: str) -> bool:
    """Return whether a message contains a recognized English or Filipino swear word."""
    text = str(message or '')
    return any(pattern.search(text) for pattern in _PROFANITY_PATTERNS)


def profanity_warning(language='english') -> str:
    """Return the localized, motorcycle-focused moderation reply."""
    language = language if language in _PROFANITY_WARNINGS else 'english'
    return (
        f"{_PROFANITY_WARNINGS[language]}\n\n"
        f"[chips: {' | '.join(profanity_chips(language))}]"
    )
