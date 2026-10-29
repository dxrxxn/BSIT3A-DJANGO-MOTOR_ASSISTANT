"""Vehicle identification, language inference and symptom intake helpers."""
from __future__ import annotations

import re

from .safety import LANGUAGE_KEYS


VEHICLE_TYPE_WORDS = {
    'motorcycle': ['motorcycle', 'motorbike', 'scooter', 'underbone', 'moped', 'motor', 'bike'],
    'car': ['car', 'sedan', 'suv', 'van', 'pickup', 'truck', 'kotse', 'awto', 'salakyan'],
    'tricycle': ['tricycle', 'trike', 'toda'],
}

SYMPTOM_WORDS = [
    'start', 'stall', 'dead', 'click', 'crank', 'battery', 'brake', 'preno', 'overheat',
    'heat', 'noise', 'tunog', 'knock', 'leak', 'tulo', 'smoke', 'usok', 'vibrat',
    'sputter', 'bog', 'hesitat', 'slip', 'clutch', 'transmission', 'chain', 'tire',
    'gulong', 'suspension', 'steer', 'manubela', 'electrical', 'charging', 'fuel',
    'gasolina', 'oil', 'langis', 'coolant', 'radiator', 'fan', 'stall', 'idle',
]

NO_START_SIGNALS = {
    'dead': [
        r'no (?:dash )?lights?', r'completely dead', r'nothing happens', r'no power',
        r'patay (?:ang )?ilaw', r'wala(?:ng)? ilaw', r'wala(?:ng)? kuryente',
        r'indi(?: gid)? magsiga', r'wala(?:ng)? suga',
    ],
    'clicking': [
        r'rapid click', r'clicking', r'click click', r'machine gun', r'nagaklik',
        r'nag-click', r'piti-piti', r'tunog relay',
    ],
    'slow_crank': [
        r'slow crank', r'cranks slowly', r'weak crank', r'turns over slowly',
        r'mabagal.*(?:ikot|tuyok|start)', r'mabug-at.*(?:ikot|tuyok)', r'mahinay.*(?:ikot|tuyok)',
    ],
    'starts_dies': [
        r'starts? (?:and|then) (?:immediately )?(?:dies|stalls|cuts out)',
        r'runs? for a (?:second|moment).*(?:dies|stalls)',
        r'nag-start.*(?:namatay|patay)', r'mag-start.*(?:mapatay|patay)',
    ],
    'cranks_no_start': [
        r'cranks? (?:normally|strongly|fine|but).*(?:not|no|won.t) start',
        r'turns over but (?:will not|won.t|does not) (?:start|fire)',
        r'no spark', r'no fuel', r'ayaw mag-start.*(?:umaandar|ikot)',
        r'nagatuyok.*(?:indi|wala).*(?:andar|start)',
    ],
}

NO_START_QUESTION_TEXT = {
    'english': 'When you press the starter, which of these happens?',
    'tagalog': 'Kapag pinindot mo ang starter, alin sa mga ito ang nangyayari?',
    'hiligaynon': 'Kon pinduton mo ang starter, diin sa sini ang nagakatabo?',
}

NO_START_OPTIONS = {
    'english': [
        'A. Completely dead — no dashboard lights',
        'B. Rapid clicking from the starter relay',
        'C. Slow cranking, like a weak battery',
        'D. Cranks normally but does not start',
        'E. Starts and immediately dies',
    ],
    'tagalog': [
        'A. Patay na patay — walang ilaw sa dashboard',
        'B. Mabilis na pag-click mula sa starter relay',
        'C. Mabagal umikot, parang mahinang baterya',
        'D. Normal ang pag-ikot pero ayaw mag-start',
        'E. Nag-start sandali tapos namatay agad',
    ],
    'hiligaynon': [
        'A. Patay gid — wala sing suga sa dashboard',
        'B. Madasig nga pag-click halin sa starter relay',
        'C. Mahinay magtuyok, daw mahina ang baterya',
        'D. Normal ang pagtuyok pero indi mag-start',
        'E. Nag-start dayon napatay gilayon',
    ],
}

NO_START_FOLLOWUP = {
    'dead': {
        'english': 'Check the battery terminals, main fuse, and ignition switch first. Do not bypass a fuse or use a larger fuse.',
        'tagalog': 'Suriin muna ang battery terminals, main fuse, at ignition switch. Huwag bypassan ang fuse o gumamit ng mas malaking fuse.',
        'hiligaynon': 'Tuluka anay ang battery terminals, main fuse, kag ignition switch. Indi pag-bypass ang fuse ukon maggamit sang mas dako nga fuse.',
    },
    'clicking': {
        'english': 'Rapid clicking often points to a weak battery or poor starter circuit connections. Measure battery voltage and inspect the relay and grounds before replacing parts.',
        'tagalog': 'Ang mabilis na pag-click ay madalas dahil sa mahinang baterya o mahinang koneksyon sa starter circuit. Sukatin ang battery voltage at suriin ang relay at grounds bago magpalit ng piyesa.',
        'hiligaynon': 'Ang madasig nga pag-click masami bangod sa mahina nga baterya ukon malain nga koneksyon sa starter circuit. Sukta ang battery voltage kag tuluka ang relay kag grounds antes mag-ilis sang parte.',
    },
    'slow_crank': {
        'english': 'Slow cranking usually needs a battery load test, terminal cleaning, and charging-system check. Do not keep cranking a weak battery for long periods.',
        'tagalog': 'Ang mabagal na pag-ikot ay karaniwang nangangailangan ng battery load test, paglilinis ng terminal, at pagsusuri ng charging system. Huwag paulit-ulit na i-crank ang mahinang baterya.',
        'hiligaynon': 'Ang mahinay nga pagtuyok masami nagakinahanglan sang battery load test, paglinis sang terminal, kag pagsusi sang charging system. Indi pagpauliton ang pag-crank sang mahina nga baterya.',
    },
    'cranks_no_start': {
        'english': 'If it cranks normally, check for spark, fuel delivery, air intake restriction, and the kill switch/sidestand sensor. Do not spray fuel or starting fluid near a hot engine.',
        'tagalog': 'Kung normal ang pag-ikot, suriin ang spark, pagpasok ng fuel, air intake, at kill switch/sidestand sensor. Huwag mag-spray ng gasolina o starting fluid malapit sa mainit na makina.',
        'hiligaynon': 'Kon normal ang pagtuyok, tuluka ang spark, pag-abot sang fuel, air intake, kag kill switch/sidestand sensor. Indi pag-spray sang gasolina ukon starting fluid malapit sa mainit nga makina.',
    },
    'starts_dies': {
        'english': 'If it starts and dies immediately, check idle speed, fuel supply, air leaks, and the sidestand/kill circuit. Note whether it dies only when cold or when hot.',
        'tagalog': 'Kung nag-start at namatay agad, suriin ang idle speed, fuel supply, air leaks, at sidestand/kill circuit. Tandaan kung namamatay lang ito kapag malamig o kapag mainit.',
        'hiligaynon': 'Kon nag-start kag napatay gilayon, tuluka ang idle speed, fuel supply, air leaks, kag sidestand/kill circuit. Tandaan kon napatay lang ini kon malamig ukon kon mainit.',
    },
}


def _history_text(conversation, limit=10):
    if conversation is None:
        return ''
    turns = list(conversation.turns.order_by('-id')[:limit])
    return ' '.join(turn.content or '' for turn in reversed(turns))


def detect_language(message, conversation=None, requested=None, client_history=None):
    if requested in ('english', 'tagalog', 'hiligaynon'):
        return requested
    from apps.core.views import _detect_language  # lazy to avoid import cycle
    history = client_history or []
    if conversation is not None:
        history = [
            {'role': 'user' if turn.role == 'user' else 'bot', 'text': turn.content or ''}
            for turn in conversation.turns.order_by('-id')[:8]
        ][::-1]
    detected = _detect_language(message, history=history)
    if detected in ('tagalog', 'hiligaynon'):
        return detected
    if conversation is not None and conversation.language in ('tagalog', 'hiligaynon'):
        return conversation.language
    return 'english'


def extract_vehicle_profile(message, conversation=None, client_history=None):
    from apps.core.views import _extract_vehicle_info  # lazy to avoid import cycle
    history = client_history or []
    if conversation is not None:
        history = [
            {'role': 'user' if turn.role == 'user' else 'bot', 'text': turn.content or ''}
            for turn in conversation.turns.order_by('-id')[:10]
        ][::-1]
    extracted = _extract_vehicle_info(message, history=history) or {}
    profile = {}
    if conversation is not None:
        conv_prof = conversation.vehicle_profile or {}
        new_make = extracted.get('make')
        new_model = extracted.get('model')
        old_make = conv_prof.get('make')
        old_model = conv_prof.get('model')
        is_switch = False
        if (new_make and old_make and new_make.lower() != old_make.lower()) or \
           (new_model and old_model and new_model.lower() != old_model.lower()):
            is_switch = True
        if not is_switch:
            profile.update(conv_prof)
    for key in ('make', 'model', 'year', 'type', 'brake_type', 'engine_fuel', 'displacement', 'variant'):
        if extracted.get(key):
            profile[key] = extracted[key]

    vehicle_type = (profile.get('vehicle_type') or profile.get('type') or '').lower()
    if vehicle_type in ('scooter', 'underbone', 'motorcycle', 'trike', 'tricycle'):
        vehicle_type = 'motorcycle' if vehicle_type != 'tricycle' else 'tricycle'
    elif vehicle_type in ('car', 'sedan', 'suv', 'van', 'pickup', 'truck', 'kotse'):
        vehicle_type = 'car'
    else:
        text = (message + ' ' + _history_text(conversation)).lower()
        for candidate, words in VEHICLE_TYPE_WORDS.items():
            if any(re.search(r'\b' + re.escape(word), text) for word in words):
                vehicle_type = candidate
                if candidate == 'motorcycle':
                    break
    profile['vehicle_type'] = vehicle_type

    if not profile.get('fuel_system'):
        fuel = (profile.get('engine_fuel') or '').lower()
        if 'fi' in fuel or 'inject' in fuel:
            profile['fuel_system'] = 'fi'
        elif 'carb' in fuel:
            profile['fuel_system'] = 'carburetor'
    if not profile.get('engine_displacement'):
        profile['engine_displacement'] = profile.get('displacement') or ''
    return profile


def vehicle_label(profile):
    return ' '.join(filter(None, [
        (profile or {}).get('year'), (profile or {}).get('make'),
        (profile or {}).get('model'), (profile or {}).get('variant'),
    ])).strip()


def has_vehicle_identity(profile):
    return bool((profile or {}).get('make') or (profile or {}).get('model') or (profile or {}).get('vehicle_type'))


def has_symptom_signal(message):
    lowered = (message or '').lower()
    return any(re.search(r'\b' + re.escape(word), lowered) for word in SYMPTOM_WORDS)


def classify_no_start(text):
    lowered = (text or '').lower()
    for key in ('dead', 'clicking', 'slow_crank', 'starts_dies', 'cranks_no_start'):
        if any(re.search(pattern, lowered) for pattern in NO_START_SIGNALS[key]):
            return key
    return None


def is_no_start_topic(text):
    lowered = (text or '').lower()
    return bool(re.search(
        r"(?:won'?t|will not|does not|doesn'?t|ayaw|indi).{0,25}(?:start|andar)|"
        r'(?:no start|starting problem|starter|crank)',
        lowered,
    ))


def missing_vehicle_questions(profile, language='english', asked_questions=None):
    """Return at most two high-value intake questions, never a wall of them."""
    profile = profile or {}
    asked = {str(item).strip().lower() for item in (asked_questions or [])}
    lang = language if language in ('english', 'tagalog', 'hiligaynon') else 'english'
    questions = []

    make = (profile.get('make') or '').strip()
    model = (profile.get('model') or '').strip()
    year = (profile.get('year') or '').strip()
    vtype = (profile.get('vehicle_type') or '').strip()

    if not make and not model:
        text = {
            'english': 'What is the vehicle make, model, and year? A photo of the badge or registration is enough if you are unsure.',
            'tagalog': 'Ano ang make, model, at taon ng sasakyan? Sapat na ang litrato ng badge o registration kung hindi ka sigurado.',
            'hiligaynon': 'Ano ang make, model, kag tuig sang salakyan? Igo na ang litrato sang badge ukon registration kon indi ka sigurado.',
        }[lang]
        questions.append({
            'question': text,
            'why': 'Vehicle-specific service information and safe checks depend on the exact model and year.',
            'options': ['Motorcycle', 'Car', 'Not sure'],
        })
        return questions

    if not vtype or vtype == 'all':
        text = {
            'english': 'Is this a motorcycle or a car?',
            'tagalog': 'Ito ba ay motorsiklo o kotse?',
            'hiligaynon': 'Ini bala motorsiklo ukon kotse?',
        }[lang]
        questions.append({'question': text, 'why': 'The diagnostic checks differ by vehicle type.', 'options': ['Motorcycle', 'Car']})

    if not year:
        text = {
            'english': 'What model year is it? If you are not sure, say “not sure” and I will avoid year-specific specifications.',
            'tagalog': 'Anong taon ang modelo? Kung hindi sigurado, sabihin ang “hindi sigurado” at iiwasan ko ang year-specific na specs.',
            'hiligaynon': 'Ano nga tuig ang modelo? Kon indi sigurado, hambala ang “indi sigurado” kag likawan ko ang year-specific nga specs.',
        }[lang]
        questions.append({'question': text, 'why': 'Model year changes parts and procedures on many vehicles.', 'options': ['Not sure']})
    return questions[:2]


def missing_symptom_questions(message, language='english', asked_questions=None):
    lang = language if language in ('english', 'tagalog', 'hiligaynon') else 'english'
    if is_no_start_topic(message):
        subtype = classify_no_start(message)
        if not subtype:
            return [{
                'question': NO_START_QUESTION_TEXT[lang],
                'why': 'The no-start path splits into battery, starter, ignition, fuel, and compression checks.',
                'options': NO_START_OPTIONS[lang],
            }]
    if not has_symptom_signal(message):
        text = {
            'english': 'What exactly happens, and when did it start? For example: “engine cranks but will not start after rain” or “front brake lever feels soft”.',
            'tagalog': 'Ano ang eksaktong nangyayari, at kailan ito nagsimula? Halimbawa: “umiiikot ang makina pero ayaw mag-start pagkatapos ng ulan” o “malambot ang front brake lever”.',
            'hiligaynon': 'Ano gid ang nagakatabo, kag san-o ini nagsugod? Halimbawa: “nagatuyok ang makina pero indi mag-start pagkatapos sang ulan” o “humok ang front brake lever”.',
        }[lang]
        return [{'question': text, 'why': 'A useful diagnosis needs the symptom, timing, and conditions.', 'options': []}]
    return []


def next_step_hint(subtype, language='english'):
    lang = language if language in ('english', 'tagalog', 'hiligaynon') else 'english'
    return NO_START_FOLLOWUP.get(subtype, {}).get(lang, '')


def stage_for(profile, message, safety, evidence, missing_questions):
    if safety and safety.get('severity') in ('warning', 'critical'):
        return 'safety'
    if missing_questions:
        if not has_vehicle_identity(profile):
            return 'identification'
        if not has_symptom_signal(message) or (is_no_start_topic(message) and not classify_no_start(message)):
            return 'symptom'
        return 'tests'
    if evidence:
        return 'diagnosis'
    return 'symptom'
