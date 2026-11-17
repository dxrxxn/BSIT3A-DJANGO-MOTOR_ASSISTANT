"""Adaptive response planning for the motorcycle assistant.

The assistant must not treat every rider as a mechanic, and it must not force
every answer into a long step-by-step format.  This module turns three inputs
into a small, deterministic response plan:

* the rider's experience level (beginner, intermediate, mechanic);
* an explanation style they explicitly asked for (simple, detailed,
  step-by-step, complete procedure, or why);
* the kind of question being asked (simple fact, troubleshooting, procedure,
  explanation, safety-critical, or general).

The plan is then rendered into prompt guidance and UI chips.  It deliberately
contains no motorcycle facts of its own: Gemini still writes the answer from
the conversation, safety assessment, and approved local evidence.  This keeps
the behaviour dynamic rather than a set of predefined answers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EXPERIENCE_LEVELS = ('beginner', 'intermediate', 'mechanic')
EXPLANATION_STYLES = ('auto', 'simple', 'detailed', 'step_by_step', 'complete', 'why')

EXPERIENCE_LABELS = {
    'beginner': 'Beginner',
    'intermediate': 'Intermediate',
    'mechanic': 'Experienced mechanic',
}

STYLE_LABELS = {
    'auto': 'Adapt automatically to the question',
    'simple': 'Simple, plain language',
    'detailed': 'More detail',
    'step_by_step': 'Step by step',
    'complete': 'Complete procedure',
    'why': 'Explain why it happens',
}

_EXPERIENCE_ALIASES = {
    'novice': 'beginner',
    'new': 'beginner',
    'newbie': 'beginner',
    'basic': 'beginner',
    'starter': 'beginner',
    'intermediate': 'intermediate',
    'medium': 'intermediate',
    'some': 'intermediate',
    'some_experience': 'intermediate',
    'some_knowledge': 'intermediate',
    'mid': 'intermediate',
    'mid_level': 'intermediate',
    'advanced': 'mechanic',
    'expert': 'mechanic',
    'experienced': 'mechanic',
    'professional': 'mechanic',
    'pro': 'mechanic',
}

_STYLE_ALIASES = {
    '': 'auto',
    'normal': 'auto',
    'default': 'auto',
    'adaptive': 'auto',
    'easy': 'simple',
    'plain': 'simple',
    'beginner': 'simple',
    'detail': 'detailed',
    'more': 'detailed',
    'more_detail': 'detailed',
    'more_details': 'detailed',
    'in_detail': 'detailed',
    'step': 'step_by_step',
    'steps': 'step_by_step',
    'stepbystep': 'step_by_step',
    'step_by_step': 'step_by_step',
    'step-by-step': 'step_by_step',
    'full': 'complete',
    'everything': 'complete',
    'reason': 'why',
    'explanation': 'why',
}

# The order matters when a message contains more than one request.  A request
# for the complete procedure wins over "step by step", and "simpler" wins over
# a generic "more details" phrase.
_STYLE_REQUEST_PATTERNS = (
    ('complete', (
        r'\b(?:complete|full|entire|whole)\s+(?:procedure|process|steps?|guide|walkthrough|instructions?|repair|job)\b',
        r'\b(?:all|every)\s+(?:the\s+)?(?:steps?|instructions?)\b',
        r'\b(?:from\s+start\s+to\s+finish|start\s+to\s+finish|everything\s+i\s+need)\b',
        r'\b(?:buong|kumpletong|lahat\s+ng)\s+(?:proseso|pamamaraan|hakbang|procedure|steps?)\b',
        r'\b(?:kompleto|bilog)\s+nga\s+(?:proseso|pamaagi|tikang)\b',
    )),
    ('step_by_step', (
        r'\bstep[\s-]*by[\s-]*step\b',
        r'\bone\s+step\s+at\s+a\s+time\b',
        r'\bwalk\s+me\s+through\b',
        r'\bguided\s+(?:steps?|procedure|walkthrough)\b',
        r'\b(?:hakbang[\s-]*hakbang|sunod[\s-]*sunod|isa[\s-]*isang\s+hakbang)\b',
        r'\b(?:tikang[\s-]*tikang|sunod[\s-]*sunod\s+nga\s+tikang)\b',
    )),
    ('simple', (
        r'\bexplain\s+(?:it\s+|that\s+|this\s+)?(?:more\s+)?(?:simply|simpler)\b',
        r'\b(?:more\s+)?simpl(?:e|er|ify)\b',
        r'\bin\s+simple\s+terms\b',
        r'\bplain\s+(?:english|language|words)\b',
        r'\blike\s+i(?:\'m|\s+am)\s+(?:a\s+)?(?:beginner|new|five|5)\b',
        r'\btoo\s+technical\b',
        r'\bi\s+(?:do\s+not|don\'?t)\s+understand\b',
        r'\b(?:mas\s+simple|simplehan|simple\s+lang)\b',
        r'\b(?:madali|madaling)\s+intindihin\b',
        r'\b(?:indi|hindi)\s+ko\s+(?:ma)?intindihan\b',
        r'\b(?:pasimplehon|pahapuson)\b',
    )),
    ('detailed', (
        r'\bmore\s+(?:details?|info|information|explanation)\b',
        r'\bin\s+detail\b',
        r'\belaborate\b',
        r'\btell\s+me\s+more\b',
        r'\bexpand\s+(?:on|the)\b',
        r'\b(?:dagdag(?:an)?|dagdagan)\s+(?:ng\s+)?(?:detalye|impormasyon)\b',
        r'\b(?:mas\s+detalyado|idetalye|detalyado)\b',
        r'\b(?:dugangi|dugang)\s+(?:sang\s+)?(?:detalye|impormasyon)\b',
    )),
    ('why', (
        r'\bexplain\s+why\b',
        r'\bwhy\s+(?:does|do|did)\s+(?:this|that|it)\s+happen(?:s|ing)?\b',
        r'\bwhy\s+is\s+(?:this|that)\s+happening\b',
        r'\b(?:bakit|baket)\s+(?:ito|iyan|ganito|nangyayari|nagyayari)\b',
        r'\bngaa\s+(?:ini|ina|amo\s+ini|nagakatabo)\b',
        r'\bano\s+ang\s+dahilan\b',
    )),
)

_REPAIR_RE = re.compile(
    r'\b(?:replace|replacing|rebuild|rebuilding|overhaul|disassemble|reassemble|'
    r'install|installing|remove|removing|bleed|bleeding|adjust|adjusting|'
    r'flush|flushing|clean|cleaning|repair|repairing|fix|fixing|change|changing|'
    r'rewire|rewiring|solder|soldering|torque|measure|measuring|test|testing|'
    r'palit|palitan|tanggal|tanggalin|ayusin|kay-uhon|linisin|ihanda|i-bleed|'
    r'ilis|kuhaon|kay-o|limpyuhon)\b',
    re.IGNORECASE,
)

_SYMPTOM_RE = re.compile(
    r'\b(?:won\'?t|will\s+not|does\s+not|doesn\'?t|not|no|hard|difficult|fails?|failed|'
    r'failing|weak|soft|spongy|dead|clicking|clicks?|cranks?|cranking|stalls?|stalling|'
    r'dies|died|misfire|misfiring|backfire|overheat|overheating|leak|leaking|smoke|'
    r'noise|noisy|knock|knocking|ticking|rattle|rattling|vibrat(?:e|ing|ion)|'
    r'squeal|squealing|grinding|slip|slipping|bogging|hesitat(?:e|ing)|loss\s+of\s+power|'
    r'problem|issue|trouble|broken|damaged|stuck|seized|overheats?|'
    r'ayaw|hindi|indi|sira|guba|tagas|tulo|usok|ingay|tunog|gahod|mahina|humok|malambot|'
    r'nag-ooverheat|namamatay|pumuputok|wala\s+hatak)\b',
    re.IGNORECASE,
)

_WHY_RE = re.compile(r'^(?:why|bakit|baket|ngaa)\b', re.IGNORECASE)

_EXPLANATION_RE = re.compile(
    r'\b(?:what\s+is|what\'s|what\s+are|explain|meaning\s+of|purpose\s+of|'
    r'function\s+of|role\s+of|how\s+does|how\s+do|how\s+is|how\s+are|'
    r'ano\s+ang|paano\s+gumagana|para\s+saan|gamit\s+ng|tungkulin\s+ng)\b',
    re.IGNORECASE,
)

_SIMPLE_QUESTION_RE = re.compile(
    r'\b(?:where|when|what|which|who|how\s+often|how\s+much|how\s+many|how\s+long|'
    r'how\s+far|is\s+it|are\s+they|can\s+i|should\s+i|do\s+i\s+need|'
    r'what\s+type|what\s+kind|what\s+size|saan|asan|nasaan|kailan|magkano|'
    r'ilang|gaano|diin|san|ano|pila|san-o)\b',
    re.IGNORECASE,
)

_MAINTENANCE_RE = re.compile(
    r'\b(?:how\s+to|how\s+do\s+i|maintenance|service|schedule|interval|'
    r'tune[\s-]?up|pms|oil\s+change|change\s+oil|palit\s+langis|'
    r'paano|unsaon|maintain)\b',
    re.IGNORECASE,
)

_FILLER_RE = re.compile(
    r'\b(?:please|pls|po|sir|ma\'?am|jarvis|can|could|would|will|you|kindly|'
    r'just|now|again|the|this|that|it|me|my|i|want|need|give|tell|show|'
    r'explain|more|a|an|to|for|about|happen|happens|happening|is|does|do|'
    r'why|how|in|terms|simple|simpler|detail|details|detailed|complete|full|'
    r'step|steps|procedure|process|guide|instructions?|instruction|'
    r'nga|man|pwede|paki|palihog|kumpleto|buong|hakbang|sunod|isa|isang|'
    r'detalyado|detalye|impormasyon|maintindihan|simplehan|bakit|baket|ngaa|dahilan|'
    r'ganito|ito|iyan|ini|ina|amo)\b',
    re.IGNORECASE,
)

_STYLE_CHIP_LABELS = {
    'english': {
        'simple': 'Explain more simply',
        'detailed': 'Give me more details',
        'step_by_step': 'Explain step by step',
        'complete': 'Complete procedure',
        'why': 'Explain why this happens',
    },
    'tagalog': {
        'simple': 'Ipaliwanag nang mas simple',
        'detailed': 'Bigyan mo ako ng mas detalyadong paliwanag',
        'step_by_step': 'Ipaliwanag nang hakbang-hakbang',
        'complete': 'Kumpletong proseso',
        'why': 'Ipaliwanag kung bakit nangyayari ito',
    },
    'hiligaynon': {
        'simple': 'Ipaliwanag sing mas simple',
        'detailed': 'Hatagi ako sang mas detalyado nga pagpaliwanag',
        'step_by_step': 'Ipaliwanag sing tikang-tikang',
        'complete': 'Kompleto nga proseso',
        'why': 'Ipaliwanag kon ngaa nagakatabo ini',
    },
}


def _norm(value):
    return re.sub(r'\s+', ' ', str(value or '').strip().lower())


def normalize_experience_level(value, *, default='beginner'):
    """Return a supported experience level without breaking older callers."""
    text = _norm(value).replace('-', '_').replace(' ', '_')
    if text in _EXPERIENCE_ALIASES:
        return _EXPERIENCE_ALIASES[text]
    if text in EXPERIENCE_LEVELS:
        return text
    return default


def normalize_explanation_style(value, *, default='auto'):
    text = _norm(value).replace('-', '_').replace(' ', '_')
    if text in _STYLE_ALIASES:
        return _STYLE_ALIASES[text]
    if text in EXPLANATION_STYLES:
        return text
    return default


def detect_explanation_style_request(message):
    """Return the style explicitly requested in this turn, or ``''``.

    A normal "why is my engine overheating?" question is *not* treated as a
    permanent style request.  Only phrases that ask for a different
    explanation format (for example "explain why this happens") count.
    """
    text = _norm(message)
    if not text:
        return ''
    for style, patterns in _STYLE_REQUEST_PATTERNS:
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            return style
    return ''


def is_style_only_message(message):
    """True when the turn is only a request to re-explain the previous answer."""
    style = detect_explanation_style_request(message)
    if not style:
        return False

    residue = _norm(message)
    for _, patterns in _STYLE_REQUEST_PATTERNS:
        for pattern in patterns:
            residue = re.sub(pattern, ' ', residue, flags=re.IGNORECASE)

    # Check for new content before removing filler words: a message such as
    # "my engine is ticking, explain more simply" is a new symptom *and* a
    # style request, not a pure re-explanation.
    topic = re.sub(r'[^a-z0-9]+', ' ', residue).strip()
    if (
        _SYMPTOM_RE.search(topic)
        or _REPAIR_RE.search(topic)
        or _EXPLANATION_RE.search(topic)
        or _SIMPLE_QUESTION_RE.search(topic)
    ):
        return False

    residue = _FILLER_RE.sub(' ', residue)
    residue = re.sub(r'[^a-z0-9]+', ' ', residue).strip()
    return len(residue.split()) <= 3


def resolve_explanation_style(requested='auto', *, detected='', stored='auto'):
    """Resolve the style for this turn and for the rest of the conversation.

    An explicit request in the current message wins, then a non-auto request
    from the client, then the style already stored on the conversation.
    ``auto`` never erases a remembered style.
    """
    if detected:
        return normalize_explanation_style(detected)
    requested = normalize_explanation_style(requested)
    if requested != 'auto':
        return requested
    return normalize_explanation_style(stored)


def classify_question_type(message, *, safety=None, style='auto'):
    """Classify what the rider is asking so the answer stays proportionate."""
    text = _norm(message)
    severity = str((safety or {}).get('severity') or 'none').lower()
    urgency = str((safety or {}).get('urgency') or '').lower()
    if (
        severity in ('warning', 'critical')
        or urgency in ('warning', 'critical', 'critical_stop')
        or (safety or {}).get('stop_use')
    ):
        return 'safety'
    if style in ('complete', 'step_by_step'):
        return 'procedure'
    if _WHY_RE.search(text):
        return 'why'
    if _SYMPTOM_RE.search(text):
        return 'troubleshooting'
    if _REPAIR_RE.search(text):
        return 'procedure'
    if _EXPLANATION_RE.search(text):
        return 'explanation'
    if _SIMPLE_QUESTION_RE.search(text) and len(text.split()) <= 18:
        return 'simple_fact'
    if _MAINTENANCE_RE.search(text):
        return 'procedure'
    return 'general'


@dataclass(frozen=True)
class ResponsePlan:
    experience_level: str
    requested_style: str
    effective_style: str
    question_type: str
    length_target: str
    structure: str
    terminology: str
    style_followup: bool = False

    def as_dict(self):
        return {
            'experience_level': self.experience_level,
            'requested_style': self.requested_style,
            'effective_style': self.effective_style,
            'question_type': self.question_type,
            'length_target': self.length_target,
            'structure': self.structure,
            'terminology': self.terminology,
            'style_followup': self.style_followup,
        }


def _effective_style(style, question_type):
    if style != 'auto':
        return style
    return {
        'simple_fact': 'simple',
        'why': 'why',
        'procedure': 'step_by_step',
        'troubleshooting': 'detailed',
        'explanation': 'detailed',
        'safety': 'simple',
    }.get(question_type, 'detailed')


def _length_target(style, question_type):
    if question_type == 'safety':
        return (
            'Keep the answer as short as safety allows: put the warning first, '
            'then only the immediate safe action and the next useful check. '
            'Never shorten away a safety warning.'
        )
    if style == 'simple':
        return (
            'Usually 1-3 short sentences (about 40-80 words). Give the direct '
            'answer and one next action. Do not add a full procedure unless the '
            'rider asked for it or safety requires it.'
        )
    if style == 'detailed':
        return (
            'Usually 3-6 sentences or a short list (about 80-180 words). Include '
            'the direct answer, the most relevant causes, and the recommended '
            'action. Add extra detail only when it changes what the rider should do.'
        )
    if style == 'step_by_step':
        return (
            'Use as many numbered steps as the job genuinely needs (usually '
            '5-12), but do not pad. One action per step, with an expected result '
            'or stop condition where useful.'
        )
    if style == 'complete':
        return (
            'Use an organised answer as long as the job needs. Include only '
            'relevant sections: direct answer, likely causes, tools/parts that '
            'are verified, the full procedure, verification, and when to stop. '
            'Do not omit a necessary step, and do not repeat the same advice.'
        )
    if style == 'why':
        return (
            'Usually 80-180 words: explain the mechanism or reason first, then '
            'what it means for the fault and the next safe action.'
        )
    return {
        'simple_fact': (
            'Usually 1-3 short sentences. Answer the exact question first; add '
            'only one useful qualification or next step.'
        ),
        'troubleshooting': (
            'Usually 80-180 words: a direct likely cause, up to 3 relevant '
            'possible causes, and the next safe check. Expand only when the '
            'rider asks for more or the safety assessment requires it.'
        ),
        'procedure': (
            'Usually 150-400 words: numbered steps for the actual job, with '
            'tools and safety notes only where they matter.'
        ),
        'explanation': (
            'Usually 60-150 words: explain the concept in plain terms, then one '
            'practical example or check.'
        ),
        'why': (
            'Usually 80-180 words: explain the mechanism first, then the '
            'practical meaning and next action.'
        ),
        'safety': (
            'Keep it as short as safety allows: warning first, then only the '
            'immediate safe action.'
        ),
    }.get(question_type, (
        'Answer directly first, then include only the detail needed for the '
        'next safe action.'
    ))


def _structure(style, question_type):
    common = (
        'Prioritise the most important information first. Do not write a long '
        'preamble, do not restate the rider\'s question, and do not add filler.'
    )
    if style == 'simple':
        return (
            'Direct answer. Only the 1-3 most relevant causes if this is a fault. '
            'One recommended next action. No long tools/parts list unless it is '
            'needed to act safely. ' + common
        )
    if style == 'detailed':
        return (
            'Direct answer, then the most relevant possible causes, then the '
            'recommended action, then additional details only when they are '
            'useful. ' + common
        )
    if style == 'step_by_step':
        return (
            'Direct answer, then numbered steps in the order the rider should do '
            'them. Include a safety note inside a step when it applies. End with '
            'how to tell whether the step worked. ' + common
        )
    if style == 'complete':
        return (
            'Direct answer, likely causes, verified tools/parts, full numbered '
            'procedure, verification, and when to stop and seek a professional. '
            'Use short headings so the rider can scan it. ' + common
        )
    if style == 'why':
        return (
            'Direct answer, then explain the mechanism or reason, then what it '
            'means for the diagnosis and the next safe action. Do not turn a '
            '"why" question into an unrequested full repair procedure. ' + common
        )
    if question_type == 'simple_fact':
        return (
            'Direct answer first. At most one qualification and one next step. '
            'Do not add a procedure or a long list. ' + common
        )
    if question_type == 'troubleshooting':
        return (
            'Direct likely cause, then only the most relevant possible causes, '
            'then the next safe check and what result to look for. ' + common
        )
    if question_type == 'procedure':
        return (
            'Direct answer, then organised steps with safety notes where they '
            'matter, then verification. ' + common
        )
    return (
        'Direct answer, then the most relevant causes or details, then the '
        'recommended next action. ' + common
    )


def _terminology(experience_level, question_type):
    if experience_level == 'mechanic':
        return (
            'Use standard technical terms, component names, and test values. '
            'Do not explain basic parts. Mark any unverified specification as '
            'unverified instead of guessing.'
        )
    if experience_level == 'intermediate':
        return (
            'Use common motorcycle terms (brake pads, chain, carb, FI, battery) '
            'without over-explaining them. Briefly define only advanced terms or '
            'abbreviations on first use.'
        )
    return (
        'Use everyday words and short sentences. When a technical term is '
        'necessary, explain it immediately in a few plain words (for example, '
        '"caliper - the clamp that squeezes the brake pads"). Do not assume the '
        'rider knows what a part does.'
    )


def build_response_plan(message, *, safety=None, experience_level='beginner',
                        style='auto', style_followup=False):
    """Create the per-turn adaptive plan used by prompts and UI chips."""
    experience = normalize_experience_level(experience_level)
    requested = normalize_explanation_style(style)
    question_type = classify_question_type(message, safety=safety, style=requested)
    effective = _effective_style(requested, question_type)
    return ResponsePlan(
        experience_level=experience,
        requested_style=requested,
        effective_style=effective,
        question_type=question_type,
        length_target=_length_target(effective, question_type),
        structure=_structure(effective, question_type),
        terminology=_terminology(experience, question_type),
        style_followup=bool(style_followup),
    )


def adaptive_prompt_block(plan):
    """Render a plan as a compact block for the Gemini prompt."""
    followup = ''
    if plan.style_followup:
        followup = (
            '\n- FOLLOW-UP: The rider is asking you to re-explain the previous '
            'answer. Keep the same diagnosis and safety warnings. Do not start a '
            'new intake and do not ask for the vehicle details again.'
        )
    return (
        'ADAPTIVE RESPONSE PLAN (server-selected; follow it exactly):\n'
        f'- Rider experience: {EXPERIENCE_LABELS.get(plan.experience_level, plan.experience_level)} '
        f'({plan.experience_level})\n'
        f'- Requested explanation style: {STYLE_LABELS.get(plan.requested_style, plan.requested_style)} '
        f'({plan.requested_style})\n'
        f'- Effective style for this turn: {STYLE_LABELS.get(plan.effective_style, plan.effective_style)} '
        f'({plan.effective_style})\n'
        f'- Question type: {plan.question_type}\n'
        f'- Length: {plan.length_target}\n'
        f'- Structure: {plan.structure}\n'
        f'- Terminology: {plan.terminology}\n'
        '- Safety override: if the local safety assessment has a warning, it '
        'must appear first and must never be shortened away, even for a one-line '
        'answer.\n'
        '- Do not mention this plan, the experience label, or the style label to '
        'the rider. Just write the answer in that style.'
        f'{followup}'
    )


def style_chips(style='auto', *, language='english', limit=3):
    """Return clickable explanation controls appropriate to the current style."""
    language = language if language in _STYLE_CHIP_LABELS else 'english'
    labels = _STYLE_CHIP_LABELS[language]
    current = normalize_explanation_style(style)
    order = ['simple', 'detailed', 'step_by_step', 'complete', 'why']
    chips = []
    for key in order:
        if key == current:
            continue
        chips.append(labels[key])
        if len(chips) >= max(0, limit):
            break
    return chips


def style_chip_to_style(text):
    """Map a UI chip label back to a style so the client can remember it."""
    normalized = _norm(text)
    for labels in _STYLE_CHIP_LABELS.values():
        for style, label in labels.items():
            if normalized == _norm(label):
                return style
    return ''
