import json
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .jarvis_translations import BRANCH_TEXTS
from .part_locations import location_hint
from .services import assistant as assistant_service
from .services.ai import fallback_model_name, is_ai_available, is_ai_configured, model_name
from .services.images import InvalidImageError, attach_to_conversation, save_uploaded_image
from .services.memory import get_or_create_conversation
from .services.rate_limit import check_rate_limit

User = get_user_model()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini AI client setup (using google-genai SDK)
# ---------------------------------------------------------------------------
_gemini_client = None
_gemini_key_warning_logged = False


def _get_gemini_client():
    """Lazily initialise and return the Gemini AI client."""
    global _gemini_client, _gemini_key_warning_logged
    if _gemini_client is not None:
        return _gemini_client

    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        if not _gemini_key_warning_logged:
            logger.warning(
                'GEMINI_API_KEY is not configured; J.A.R.V.I.S. will use offline fallbacks.'
            )
            _gemini_key_warning_logged = True
        return None

    from google import genai
    try:
        _gemini_client = genai.Client(
            api_key=api_key,
            http_options={'timeout': 45000}
        )
    except Exception:
        try:
            _gemini_client = genai.Client(api_key=api_key)
        except Exception as exc:
            logger.warning('Could not initialise the Gemini client: %s', exc)
            return None
    return _gemini_client

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


def _reset_lock_state(request):
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


def _get_lock_state(request):
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        _reset_lock_state(request)
        return 0, None

    if timezone.now() < unlock_time:
        remaining = int((unlock_time - timezone.now()).total_seconds())
        return failed_attempts, remaining

    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request):
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


def _validate_registration_data(data):
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not username:
        errors['username'] = 'Username is required.'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already taken.'

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if User.objects.filter(email=email).exists():
                errors['email'] = 'Email already registered.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    else:
        try:
            validate_password(password)
        except ValidationError as exc:
            errors['password'] = ' '.join(exc.messages)

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    return errors


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    if request.method == 'GET':
        return render(request, 'auth/login.html')

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)

    if user is not None:
        _reset_lock_state(request)
        login(request, user)
        return redirect('dashboard')

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def home(request):
    if not request.user.is_authenticated:
        if getattr(settings, 'IS_TESTING', False):
            return redirect('login')
        # Development convenience only; never create a known-password account
        # in normal or production use.
        if getattr(settings, 'DEBUG', False) and getattr(settings, 'AUTO_LOGIN_DEV', False):
            dev_user = User.objects.filter(is_superuser=True).order_by('id').first()
            if dev_user:
                login(request, dev_user)
            else:
                messages.error(request, 'AUTO_LOGIN_DEV is enabled but no superuser exists. Run createsuperuser first.')
                return redirect('login')
        else:
            return redirect('login')

    from apps.motor.models import DiagnosticSymptom

    query = request.GET.get('q', '').strip()[:150]
    symptoms = DiagnosticSymptom.objects.all()
    diagnostic_results = []

    if query:
        matched_symptoms = symptoms.filter(
            Q(symptom_name__icontains=query)
            | Q(category__icontains=query)
            | Q(description__icontains=query)
            | Q(troubleshooting_guides__possible_cause__icontains=query)
            | Q(troubleshooting_guides__repair_instructions__icontains=query)
            | Q(troubleshooting_guides__advice_notes__icontains=query)
            | Q(
                troubleshooting_guides__required_parts__part__part_name__icontains=query
            )
        ).distinct().prefetch_related(
            'troubleshooting_guides__required_parts__part'
        )

        for symptom in matched_symptoms:
            guides = []
            for guide in symptom.troubleshooting_guides.all():
                repair_steps = [
                    re.sub(
                        r'^\s*(?:step\s*)?\d+[\.\):\-]\s*',
                        '',
                        step.strip(),
                        flags=re.IGNORECASE,
                    )
                    for step in guide.repair_instructions.splitlines()
                    if step.strip()
                ]
                if not repair_steps and guide.repair_instructions.strip():
                    repair_steps = [guide.repair_instructions.strip()]

                guides.append({
                    'guide': guide,
                    'repair_steps': repair_steps,
                    'required_parts': [
                        requirement
                        for requirement in guide.required_parts.all()
                    ],
                })

            diagnostic_results.append({
                'symptom': symptom,
                'guides': guides,
            })

    return render(request, 'home.html', {
        'query': query,
        'diagnostic_results': diagnostic_results,
        'quick_symptoms': symptoms.order_by('symptom_name')[:3],
    })


@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'GET':
        return render(request, 'auth/register.html')

    form_data = {
        'username': request.POST.get('username', ''),
        'first_name': request.POST.get('first_name', ''),
        'last_name': request.POST.get('last_name', ''),
        'email': request.POST.get('email', ''),
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
    }

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {'errors': errors, 'form_data': form_data})

    user = User.objects.create_user(
        username=form_data['username'].strip(),
        first_name=form_data['first_name'].strip(),
        last_name=form_data['last_name'].strip(),
        email=form_data['email'].strip(),
        password=form_data['password'],
    )
    login(request, user)
    messages.success(request, 'Welcome to Motor Assistant! Your account has been created.')
    return redirect('dashboard')


# ---------------------------------------------------------------------------
# Jarvis AI Chat
# ---------------------------------------------------------------------------

def _jarvis_address(user):
    first = (getattr(user, 'first_name', '') or '').strip()
    return first if first else 'sir'


FALLBACK_CHIPS = {
    'visual': {
        'english': 'What is a caliper? | What is a sprocket? | What is a spark plug? | What is a headlight?',
        'tagalog': 'Ano ang caliper? | Ano ang sprocket? | Ano ang spark plug? | Ano ang headlight?',
        'hiligaynon': 'Ano ang caliper? | Ano ang sprocket? | Ano ang spark plug? | Ano ang headlight?',
    },
    'diagnostic': {
        'english': "Engine won't start | Front brake not working | Engine overheating | Strange engine noise",
        'tagalog': 'Ayaw mag-start ng makina | Sira ang preno | Umainit ang makina | Kakaibang ingay sa makina',
        'hiligaynon': 'Indi mag-andar ang makina | Guba ang preno | Naga-init ang makina | May kakaiba nga tingog ang makina',
    },
    'general': {
        'english': 'How often should I change oil? | What to check before changing a tire? | How to clean and lube the chain? | Brake maintenance checklist | Full maintenance schedule',
        'tagalog': 'Kailan dapat mag-change oil? | Ano ang titingnan bago magpalit ng gulong? | Paano linisin at lagyan ng langis ang chain? | Brake maintenance checklist | Buong maintenance schedule',
        'hiligaynon': 'San-o dapat mag-ilis sang langis? | Ano ang usisahon antes mag-ilis sang gulong? | Paano limpyohan kag butangan sang lana ang chain? | Brake maintenance checklist | Bug-os nga maintenance schedule',
    },
}


# Offline answers for general motorcycle questions. These are intentionally
# practical and conservative: typical intervals are given as ranges, and the
# owner's manual is always named as the final authority.
GENERAL_FALLBACK_TEXTS = {
    'oil': (
        "**Engine oil change — quick answer, {sir}:**\n\n"
        "**Interval:** Usually every **2,000–4,000 km** or **3–6 months** for a daily scooter/underbone. "
        "Hard use (heavy traffic, short trips, dusty roads) → closer to 2,000 km; highway touring → up to 4,000 km. "
        "Your owner's manual is the final authority for your exact model.\n\n"
        "**Oil type:** JASO MA/MA2 4T motorcycle oil in the viscosity listed in your manual. "
        "Do not use passenger-car oil with friction modifiers in a wet-clutch motorcycle.\n\n"
        "**Before you start:** drain pan, correct wrench/socket, new crush washer, oil filter, funnel, "
        "gloves, and a sealed container for the used oil. Park on level ground.\n\n"
        "**Procedure:**\n"
        "- [ ] 1. Warm the engine for 2–3 minutes, shut it off, then wait 2–3 minutes.\n"
        "- [ ] 2. Keep the bike upright on level ground and place the drain pan under the drain bolt.\n"
        "- [ ] 3. Remove the drain bolt (and filter); let the old oil drain completely.\n"
        "- [ ] 4. Fit a new crush washer and reinstall the drain bolt snugly — do not overtighten; use the manual torque if you have a wrench.\n"
        "- [ ] 5. Replace the oil filter as the manual specifies; lubricate the filter seal with fresh oil.\n"
        "- [ ] 6. Refill with the specified amount, check the sight glass/dipstick, then run the engine briefly.\n"
        "- [ ] 7. Stop the engine, wait a minute, recheck the level, and look for leaks.\n\n"
        "**Safety and disposal:** Used oil is toxic — seal it and take it to a recycling center; never dump it. "
        "If the drain bolt is rounded or seized, or you find metal flakes in the oil, stop and have a mechanic inspect it.\n\n"
        "[chips: How often should I change oil? | What oil type should I use? | What to check before changing a tire? | Full maintenance schedule]"
    ),
    'tire': (
        "**Before changing a tyre, check these, {sir}:**\n\n"
        "1. **Size and rating:** Read the sidewall (for example 90/80-14) and confirm the replacement matches. "
        "Check the load and speed rating, and whether your rim needs a tube or is tubeless.\n"
        "2. **Tyre condition:** Tread depth at least **1.6 mm**, no cracks, bulges, or embedded nails/screws. "
        "Inspect the rim for bends, cracks, or corrosion.\n"
        "3. **Tools:** Tyre levers, rim protectors, bead breaker (or a shop), torque wrench, new valve stem if needed, "
        "pump with gauge, and soapy water for leak checks.\n"
        "4. **Brake and chain clearance:** Make sure the disc rotor is not bent, pads are not contaminated, and the chain/sprocket "
        "has room to move. On drum brakes, note the shoe and spring orientation before disassembly.\n"
        "5. **Wheel bearings and spokes:** Rock the wheel for play and check that spokes are tight. "
        "Keep the axle nut, spacers, and adjusters in order.\n"
        "6. **Safety:** Support the bike securely on a center stand or paddock stand, chock the other wheel, "
        "and keep hands clear of a spinning wheel. Use a torque wrench on the axle — do not guess.\n"
        "7. **After fitting:** Seat the bead, inflate to the pressure on the tyre/owner's manual, check for leaks with soapy water, "
        "spin the wheel, and test the brakes slowly in a safe area before riding normally.\n\n"
        "**Tip:** Replace tyres in pairs when wear is uneven, and recheck pressure cold the next morning. "
        "If the rim is cracked or the axle threads are damaged, stop and let a shop handle it.\n\n"
        "[chips: What tyre pressure should I use? | How often should I change oil? | Brake maintenance checklist | Full maintenance schedule]"
    ),
    'chain': (
        "**Chain care, {sir}:**\n\n"
        "- **Clean and lube:** Every **500 km** or after rain. Use a chain cleaner and dedicated chain lube — "
        "WD-40 is a cleaner/water displacer, not a substitute for chain lubricant.\n"
        "- **Slack:** Typically **20–35 mm** at the midpoint (confirm your manual). Adjust at the rear axle and keep the wheel aligned.\n"
        "- **Inspect:** Tight links, rust, missing O-rings, and hooked or sharp sprocket teeth. "
        "If the chain is worn, replace the chain and sprockets as a set — a new chain on worn sprockets wears out fast.\n"
        "- **Safety:** Engine off, transmission in neutral, fingers away from the sprocket, and use a paddock stand. "
        "Do not overtighten the chain; it can damage the countershaft bearing.\n\n"
        "**Quick check:** With the bike on its stand, spin the rear wheel slowly and watch the chain run. "
        "A dry or kinked chain will show tight spots as it passes over the sprocket.\n\n"
        "[chips: How often should I change oil? | What to check before changing a tire? | Brake maintenance checklist | Full maintenance schedule]"
    ),
    'brakes': (
        "**Brake maintenance checklist, {sir}:**\n\n"
        "- **Pads/shoes:** Check every **2,000–4,000 km** or monthly. Replace disc pads at about **2 mm** of lining; "
        "replace drum shoes when the friction material is thin or contaminated.\n"
        "- **Fluid:** Check the reservoir level and colour. Bleed the system every **1–2 years**, or sooner if the lever feels spongy. "
        "Use the DOT 3/DOT 4 fluid specified on the cap — never mix types.\n"
        "- **Disc/drum:** Look for deep grooves, blue heat spots, or a warped rotor. The lever/pedal should feel firm and hold pressure.\n"
        "- **Leaks:** Check the master cylinder, hose, caliper, and banjo bolts for wet spots or crusty residue.\n"
        "- **Safety:** Do not ride if the lever sinks, fluid is leaking, or you hear metal grinding. "
        "Brake dust is harmful — wear gloves and a mask, and work in a ventilated area.\n\n"
        "**When to stop:** If a brake line is cracked, a caliper piston is seized, or the rotor is below the minimum thickness, "
        "replace the affected parts instead of adjusting around the problem.\n\n"
        "[chips: How often should I change oil? | What to check before changing a tire? | How to clean and lube the chain? | Full maintenance schedule]"
    ),
    'schedule': (
        "**Routine motorcycle maintenance schedule, {sir}:**\n\n"
        "- **Before every ride:** Tyres, brakes, lights, chain, and a quick look for leaks.\n"
        "- **Weekly:** Cold tyre pressure, chain lubrication, engine oil level, brake fluid level, and coolant level (if liquid-cooled).\n"
        "- **Every 2,000–4,000 km:** Engine oil and filter, air-filter check, chain adjustment, brake inspection.\n"
        "- **Every 4,000–6,000 km:** Spark plug, valve-clearance check (if applicable), CVT inspection on scooters.\n"
        "- **Every 8,000–12,000 km:** CVT belt and rollers, brake fluid, fork oil, wheel bearings, and suspension check.\n"
        "- **Yearly or per manual:** Coolant replacement, brake fluid flush, battery check, and a full fastener/torque check.\n\n"
        "**Important:** These are typical intervals for everyday riding. Traffic, dust, rain, and hard riding shorten them; "
        "the owner's manual and the condition of the parts are the final authority. "
        "If you ride in heavy traffic or on dusty roads, move oil and air-filter service closer to the shorter interval.\n\n"
        "[chips: How often should I change oil? | What to check before changing a tire? | How to clean and lube the chain? | Brake maintenance checklist]"
    ),
    'help': (
        "I can help with any motorcycle question, {sir} — not only breakdowns. "
        "Here are quick baselines you can use right away:\n\n"
        "- **Oil/filter:** 2,000–4,000 km or 3–6 months; JASO MA/MA2 4T oil; filter per manual.\n"
        "- **Tyres:** Check cold pressure weekly (often around 29–33 psi front / 33–36 psi rear), tread at least 1.6 mm, "
        "and no cracks, bulges, or nails.\n"
        "- **Chain:** Clean and lube every 500 km; 20–35 mm slack; replace chain and sprockets together when worn.\n"
        "- **Brakes:** Pads at least 2 mm, fluid clear and at level, firm lever; bleed every 1–2 years or if spongy.\n"
        "- **Battery:** 12.6 V+ at rest, 13.5–14.5 V while charging; typical life 3–5 years.\n"
        "- **CVT:** Inspect the belt and rollers around 8,000–12,000 km; replace per wear and manual.\n"
        "- **Coolant:** Check cold monthly; replace every 2 years or per manual.\n\n"
        "Tell me your bike model (optional) and what you want to do — oil change, tyre change, chain care, brake check, "
        "or a full service — and I'll give you the interval, tools, steps, and safety notes. "
        "The owner's manual is always the final authority for exact specs.\n\n"
        "[chips: How often should I change oil? | What to check before changing a tire? | How to clean and lube the chain? | Brake maintenance checklist | Full maintenance schedule]"
    ),
}


def _general_topic(message):
    """Pick the offline general-answer topic from a free-text question."""
    msg = (message or '').lower()

    def has(*words):
        return any(re.search(r'\b' + re.escape(w) + r'\b', msg) for w in words)

    if has('oil', 'langis', 'lana', 'lubricant'):
        return 'oil'
    if has('tyre', 'tire', 'gulong', 'wheel', 'rim'):
        return 'tire'
    if has('chain', 'kadena', 'sprocket'):
        return 'chain'
    if has('brake', 'preno', 'caliper', 'brake pad', 'shoe'):
        return 'brakes'
    if has(
        'maintenance', 'maintain', 'service', 'pms', 'tune up', 'tune-up',
        'schedule', 'interval', 'check', 'inspection', 'care',
    ):
        return 'schedule'
    return 'help'


def _history_plain_text(history):
    if not history:
        return ''
    if isinstance(history, str):
        return history
    parts = []
    for turn in list(history)[-8:]:
        if isinstance(turn, dict):
            parts.append(str(turn.get('text') or ''))
        else:
            parts.append(str(turn))
    return ' '.join(part for part in parts if part)


def _general_location_fallback(message, sir, history=None):
    """Offline answer for "where is the ...?" questions."""
    hint = location_hint(message) or location_hint(_history_plain_text(history))
    if hint:
        return (
            f"**Typical location, {sir}:**\n\n"
            f"{hint}\n\n"
            "The exact position varies by model, so confirm it in your owner's "
            "manual before removing panels or disconnecting anything.\n\n"
            "[chips: Oil filter | Battery | Fuse box | ECU/CDI | Horn]"
        )
    return (
        "I can point you to the usual location. Which part do you mean?\n\n"
        "Common ones are the oil filter, battery, fuse box, ECU/CDI, horn, and "
        "starter relay.\n\n"
        "[chips: Oil filter | Battery | Fuse box | ECU/CDI | Horn]"
    )


def _jarvis_general_fallback(message, user, history=None, language=None):
    """Offline answer for maintenance/how-to/info questions (no intake form)."""
    sir = _jarvis_address(user)
    lang = language if language in ('english', 'tagalog', 'hiligaynon') else _detect_language(message, history)
    if re.search(r'\b(?:where|saan|asa|diin)\b', message or '', re.IGNORECASE):
        if (
            location_hint(message)
            or location_hint(_history_plain_text(history))
            or re.search(r'\b(?:parts?|components?)\b', message or '', re.IGNORECASE)
        ):
            localized = _localized_branch('general_location', lang, sir=sir)
            if localized:
                return localized
            return _general_location_fallback(message, sir, history)
    topic = _general_topic(message)
    localized = _localized_branch(f'general_{topic}', lang, sir=sir)
    if localized:
        return localized
    return GENERAL_FALLBACK_TEXTS[topic].format(sir=sir)


def _localized_branch(key, lang, **ctx):
    """Localized offline fallback text for a branch, or None for English/missing keys."""
    lang_key = {'tagalog': 'tl', 'hiligaynon': 'hil'}.get(lang)
    if not lang_key:
        return None
    template = BRANCH_TEXTS.get(key, {}).get(lang_key)
    if not template:
        return None
    # Placeholder replacement (not str.format) so templates may contain JSON
    # vehicle-form tags with literal braces.
    out = template
    for placeholder, value in ctx.items():
        out = out.replace('{' + placeholder + '}', str(value))
    return out


def _detect_language(text, history=None):
    """Detects whether the dialogue is primarily English, Tagalog, or Hiligaynon."""
    corpus = (text or '').lower()
    if history and isinstance(history, list):
        for turn in history[-4:]:
            corpus += " " + (turn.get('text', '') or '').lower()

    hiligaynon_words = [
        'maayong', 'adlaw', 'hapon', 'aga', 'gab-i', 'ngaa', 'bala', 'indi', 'mag-andar',
        'guba', 'preno', 'tambutso', 'makina', 'piti-piti', 'nagapiti-piti', 'nagasiga',
        'nagatulo', 'wala', 'akon', 'imo', 'subong', 'tani', 'sini', 'sining', 'kay-uhon',
        'humok', 'nagadul-ong', 'matig-a', 'manubela', 'baskog', 'buhin'
    ]
    tagalog_words = [
        'kamusta', 'kumusta', 'bakit', 'ayaw', 'hindi', 'mag-start', 'umaandar',
        'preno', 'tambutso', 'makina', 'malambot', 'lumulubog', 'matigas', 'maingay',
        'umuusok', 'usok', 'paano', 'salamat', 'kasi', 'sasakyan', 'kotse', 'kumatok',
        'baterya', 'langis', 'gulong', 'mekaniko', 'talyer', 'gagawin', 'susunod'
    ]

    h_score = sum(1 for w in hiligaynon_words if re.search(r'\b' + re.escape(w) + r'\b', corpus))
    t_score = sum(1 for w in tagalog_words if re.search(r'\b' + re.escape(w) + r'\b', corpus))

    if h_score >= 2 or (h_score > 0 and h_score >= t_score and any(w in corpus for w in ['maayong', 'ngaa', 'indi', 'guba', 'subong'])):
        return 'hiligaynon'
    if t_score >= 1 or any(w in corpus for w in ['kamusta', 'bakit', 'ayaw', 'hindi', 'paano']):
        return 'tagalog'
    return 'english'


def _extract_vehicle_info(text, history=None):
    """Extracts known vehicle specifications from current message and conversation history."""
    current_text = (text or '').lower()
    history_turns = []
    if history and isinstance(history, list):
        for turn in history:
            if isinstance(turn, dict):
                role = str(turn.get('role', '')).lower()
                if role in ('bot', 'assistant', 'system'):
                    continue
                history_turns.append((turn.get('text', '') or '').lower())
            elif isinstance(turn, str):
                history_turns.append(turn.lower())
    history_corpus = " ".join(history_turns)
    corpus = (current_text + " " + history_corpus).strip()

    info = {
        'make': None,
        'model': None,
        'year': None,
        'type': None,
        'brake_type': None,
        'engine_fuel': None,
        'displacement': None,
    }

    # 1. Direct parsing for structured form submissions
    form_match = re.search(r'Vehicle:\s*(?:(\d{4})\s+)?([A-Za-z]+)\s+([^\(\n,]+)', text or '', re.I)
    if form_match:
        y, mk, mdl = form_match.groups()
        if y:
            info['year'] = y.strip()
        if mk:
            info['make'] = mk.strip().title()
        if mdl:
            info['model'] = mdl.strip().title()

    makes = [
        'honda', 'yamaha', 'suzuki', 'kawasaki', 'toyota', 'mitsubishi', 'nissan',
        'ford', 'hyundai', 'isuzu', 'mazda', 'bmw', 'ducati', 'ktm', 'vespa',
        'tvs', 'bajaj', 'kymco', 'sym', 'rusi', 'motorstar', 'keeway', 'royal enfield'
    ]

    # Prioritize make in current message before checking conversation history
    make_switched = False
    if not info['make']:
        for m in makes:
            if re.search(r'\b' + re.escape(m) + r'\b', current_text):
                info['make'] = m.title()
                make_switched = True
                break
        if not info['make'] and history_turns:
            for turn_txt in reversed(history_turns):
                for m in makes:
                    if re.search(r'\b' + re.escape(m) + r'\b', turn_txt):
                        info['make'] = m.title()
                        break
                if info['make']:
                    break

    models_list = [
        'click 125i', 'click 150i', 'click 160', 'click',
        'aerox 155', 'aerox', 'nmax 155', 'nmax',
        'raider 150', 'raider', 'mio sporty', 'mio i 125', 'mio gear', 'mio soul', 'mio',
        'fazzio', 'gravis', 'burgman street', 'burgman',
        'beat', 'pcx 160', 'pcx 150', 'pcx', 'adv 160', 'adv 150', 'adv',
        'sniper 155', 'sniper 150', 'sniper',
        'tmx 125', 'tmx supremo', 'tmx', 'barako 175', 'barako',
        'bajaj ct 100', 'bajaj ct100', 'ct 100', 'ct100', 'ct 125', 'ct125',
        'kawasaki ct100', 'kawasaki ct 100',
        'rouser 200', 'rouser 160', 'rouser 135', 'rouser',
        'boxer 150', 'discover 125', 'pulsar 200', 'pulsar 150', 'pulsar',
        'wave 110', 'wave 125', 'wave', 'xrm 125', 'xrm', 'smash 115', 'smash',
        'vios', 'mirage g4', 'mirage', 'wigo', 'innova', 'fortuner', 'hilux',
        'civic', 'corolla', 'city', 'almera', 'rush', 'raize', 'montero'
    ]

    # Prioritize model in current message before checking conversation history
    model_switched = False
    if not info['model']:
        for mdl in models_list:
            mdl_match = re.search(r'\b' + re.escape(mdl) + r'\b', current_text)
            if mdl_match:
                label = mdl_match.group(0).title()
                label = re.sub(r'(\d+)I\b', r'\1i', label)
                if 'ct' in label.lower():
                    label = re.sub(r'\bCt\b', 'CT', label)
                    label = re.sub(r'\bCt(\d+)', r'CT \1', label)
                info['model'] = label
                model_switched = True
                # If make wasn't explicitly stated, infer make from brand-specific model
                if not info['make']:
                    if any(k in mdl for k in ['ct 100', 'ct100', 'rouser', 'boxer', 'pulsar', 'discover']):
                        info['make'] = 'Bajaj'
                    elif any(k in mdl for k in ['click', 'beat', 'pcx', 'adv', 'wave', 'xrm', 'tmx']):
                        info['make'] = 'Honda'
                    elif any(k in mdl for k in ['aerox', 'nmax', 'mio', 'fazzio', 'gravis', 'sniper']):
                        info['make'] = 'Yamaha'
                    elif any(k in mdl for k in ['raider', 'smash', 'burgman']):
                        info['make'] = 'Suzuki'
                    elif any(k in mdl for k in ['barako']):
                        info['make'] = 'Kawasaki'
                break

        if not info['model'] and history_turns:
            for turn_txt in reversed(history_turns):
                for mdl in models_list:
                    mdl_match = re.search(r'\b' + re.escape(mdl) + r'\b', turn_txt)
                    if mdl_match:
                        label = mdl_match.group(0).title()
                        label = re.sub(r'(\d+)I\b', r'\1i', label)
                        if 'ct' in label.lower():
                            label = re.sub(r'\bCt\b', 'CT', label)
                            label = re.sub(r'\bCt(\d+)', r'CT \1', label)
                        info['model'] = label
                        break
                if info['model']:
                    break

    if info['make'] and info['model'] and info['model'].lower().startswith(info['make'].lower()):
        info['model'] = info['model'][len(info['make']):].strip()

    # Determine attribute scope: if the user named a new make or model in the current message,
    # do NOT inherit old incompatible attributes from previous turns
    active_attr_text = current_text if (make_switched or model_switched) else corpus

    if not info['year']:
        year_match = re.search(r'\b(19[89]\d|20[012]\d)\b', active_attr_text)
        if year_match:
            info['year'] = year_match.group(1)

    # Type detection
    if any(k in active_attr_text for k in ['scooter', 'click', 'aerox', 'nmax', 'mio', 'beat', 'pcx', 'adv', 'fazzio', 'burgman']):
        info['type'] = 'scooter'
    elif any(k in active_attr_text for k in ['car', 'sedan', 'suv', 'van', 'truck', 'kotse', 'awto', 'salakyan', 'vios', 'wigo']):
        info['type'] = 'car'
    elif any(k in active_attr_text for k in ['tricycle', 'toda', 'trike']):
        info['type'] = 'tricycle'
    elif any(k in active_attr_text for k in ['motorcycle', 'motor', 'bike', 'underbone', 'ct 100', 'ct100', 'tmx', 'barako', 'rouser', 'boxer']):
        info['type'] = 'motorcycle'

    # Brake detection
    if 'disc' in active_attr_text or 'disk' in active_attr_text or 'caliper' in active_attr_text:
        info['brake_type'] = 'disc'
    elif 'drum' in active_attr_text or 'tambor' in active_attr_text or (info['model'] and any(k in info['model'].lower() for k in ['ct 100', 'ct100', 'barako', 'tmx'])):
        info['brake_type'] = 'drum'

    # Fuel system detection
    if re.search(r'\b(?:fi|efi|pgm-fi)\b|fuel inject|inject(?:ed|ion)', active_attr_text):
        info['engine_fuel'] = 'FI'
    elif re.search(r'\bcarbs?\b|\bcarburetor\b|karburador', active_attr_text) or (info['model'] and any(k in info['model'].lower() for k in ['ct 100', 'ct100', 'barako', 'tmx 125', 'wave 110', 'xrm 125'])):
        info['engine_fuel'] = 'Carburetor'

    disp_match = re.search(r'\b(\d{2,4}\s?cc|\d\.\d\s?[lL])\b', active_attr_text)
    if disp_match:
        info['displacement'] = disp_match.group(1).upper()
    elif info['model'] and ('ct 100' in info['model'].lower() or 'ct100' in info['model'].lower()):
        info['displacement'] = '100CC'
        info['type'] = info['type'] or 'motorcycle'
        info['engine_fuel'] = info['engine_fuel'] or 'Carburetor'

    return info


def _jarvis_gemini_general(message, user, history=None, language=None):
    """Broad motorcycle-assistant call for maintenance/how-to/info questions."""
    client = _get_gemini_client()
    if client is None:
        return None

    sir = _jarvis_address(user)
    # Detect/normalise language
    if not language or language not in ('english', 'tagalog', 'hiligaynon'):
        language = _detect_language(message, history)
    _LANG_LABELS = {
        'english': 'English',
        'tagalog': 'Filipino / Tagalog',
        'hiligaynon': 'Hiligaynon / Ilonggo',
    }
    lang_label = _LANG_LABELS.get(language, 'English')


    convo_history_str = ""
    if history and isinstance(history, list):
        formatted_turns = []
        for turn in history[-16:]:
            r = "User" if turn.get('role') == 'user' else "J.A.R.V.I.S."
            txt = turn.get('text', '').strip()
            txt = re.sub(r'\[chips:.*?\]', '', txt).strip()
            if txt:
                formatted_turns.append(f"{r}: {txt}")
        if formatted_turns:
            convo_history_str = (
                "\n## PREVIOUS CONVERSATION TURNS (use any vehicle details the user already gave; do not re-ask them):\n"
                + "\n".join(formatted_turns)
                + "\n"
            )

    full_prompt = f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), a master motorcycle mechanic, maintenance coach, and riding advisor. You speak like Tony Stark's assistant: professional, courteous, precise, witty, and safety-first. Address the user respectfully as '{sir}'.
## MANDATORY LANGUAGE INSTRUCTION
DETECTED LANGUAGE: {lang_label} ({language})
YOU MUST RESPOND ENTIRELY IN {lang_label.upper()}. This is non-negotiable. Keep technical part names (e.g. brake caliper, CVT, spark plug, ECU) in their original English form and explain them simply in the response language.


The user is asking a GENERAL motorcycle question — maintenance, how-to, service intervals, pre-ride/pre-repair checks, tools, parts, riding technique, buying advice, comparisons between models, riding gear/safety equipment, or general information about a motorcycle model. They are not necessarily reporting a breakdown.

## RESPONSE RULES
1. ANSWER DIRECTLY FIRST. Give the answer or recommendation in the first 1–3 sentences. Never open by asking for the make, model, or year.
2. DO NOT request vehicle intake and NEVER emit `[vehicle-form: ...]`. If an exact specification depends on the bike, give the typical range and say "confirm in your owner's manual" instead of inventing a number.
3. MATCH THE DEPTH TO THE QUESTION. For a simple interval or spec question, answer directly and briefly — no full tutorial unless the user asks for one. For a full how-to, include the interval, tools/parts, a short `- [ ] 1. ...` checklist, and safety notes.
4. For "what should I check before changing X" questions, give a pre-check list: condition, size/fitment, tools, safety, and post-fit checks.
4b. For COMPARISON questions (e.g. "Aerox vs NMAX", "which is better X or Y"):
   - Give an objective side-by-side comparison: engine, features, target user, riding style, price range.
   - State which is better FOR WHAT USE CASE, not an absolute winner.
4c. For "tell me about [bike]" / model info questions:
   - Brief overview: type, displacement, fuel system, key features, pros/cons, and common maintenance points.
4d. For BUYING / RECOMMENDATION questions ("best motorcycle for beginners", "what should I buy"):
   - Give 2–3 concrete recommendations with a brief reason each (budget, skill level, use case, parts availability).
4e. For RIDING GEAR / SAFETY EQUIPMENT questions ("what helmet", "what gear to wear"):
   - Recommend gear appropriate to the use case (commuting, sport, touring).
   - Always mention helmet safety standards (DOT/ECE/SNELL) and the ATGATT principle.
5. Never refuse a motorcycle-related question. If you do not know an exact figure, say so and give safe general guidance. Never invent torque values, clearances, fluid capacities, or part numbers.
6. Use any vehicle details already present in the conversation. If none are known, keep the advice general — do not demand them.
7. Match the user's language: English, Tagalog/Taglish, or Hiligaynon. Keep technical terms natural (oil, chain, brake pads, CVT, coolant).
8. End with 3–5 clickable chips in the exact format `[chips: Option 1 | Option 2 | Option 3]`.
9. Do not emit `[part-image: ...]` unless the user explicitly asks for a picture.
10. Be conversational and context-aware. Acknowledge the user's previous message when it matters, build on it, and never repeat a previous answer verbatim.
11. If the user asks a follow-up, answer that follow-up first. Do not restart the conversation or re-ask for details already in the history.
12. For "where is X located?" questions, give the typical location first, then note that it varies by model and tell the user to confirm in the owner's manual. Do not ask for make/model/year before giving the typical location.
13. If the user says "that part" or "it", use the part mentioned in the previous turn. If the part is genuinely unclear, ask which part they mean and offer 3–5 example chips — never repeat a generic capabilities answer.

## TYPICAL BASELINES (ranges only — confirm the owner's manual)
- Engine oil: every 2,000–4,000 km or 3–6 months for everyday scooters/underbones; sooner in heavy traffic, short trips, or dusty conditions. Use JASO MA/MA2 4T motorcycle oil; replace the filter per manual.
- Tyres: check cold pressure weekly (often around 29–33 psi front / 33–36 psi rear), tread at least 1.6 mm, no cracks/bulges/nails.
- Chain: clean and lube every 500 km or after rain; 20–35 mm slack at the midpoint; replace chain and sprockets together when worn.
- Brakes: pads at least 2 mm; check fluid level/colour; bleed every 1–2 years or when spongy; never ride with a sinking lever or a leak.
- CVT: inspect belt/rollers around 8,000–12,000 km; replace per wear and manual.
- Air filter: clean every 2,000–4,000 km; replace per manual.
- Spark plug: inspect/clean every 4,000–6,000 km; replace per manual.
- Battery: 12.6 V+ at rest, 13.5–14.5 V charging; typical life 3–5 years.
- Coolant: check cold monthly; replace every 2 years or per manual.
- Suspension/steering: check for leaks, play, and uneven tyre wear at every service.

## COMMON COMPONENT LOCATIONS (typical motorcycle/scooter layout; confirm on the specific model)
- Oil filter: side or bottom of the engine crankcase, behind a circular cover or as an external spin-on canister.
- Air filter: inside the airbox, usually under the seat or behind a side panel.
- Battery: under the seat, behind a side panel, or under the front fairing on some scooters.
- Spark plug: top/center of the cylinder head, sometimes under the fuel tank or a small access cover.
- Main fuse / fuse box: near the battery, under the seat, or behind a side cover.
- ECU/CDI: under the seat, near the battery, behind a side panel, or under the front fairing; layout varies widely.
- Horn: near the front fork, behind the front panel, or close to the headlight/radiator.
- Starter relay/solenoid: near the battery, usually under the seat or behind a side cover.
- Fuel pump: inside the fuel tank on EFI bikes; near the tank on carbureted bikes.
- Fuel filter: inline under the tank or near the fuel pump; some are inside the tank.
- Regulator/rectifier: behind a front panel or near the battery; follow the wiring from the stator.
- Chain: left side of the rear wheel and swingarm.
- Brake pads/caliper: at the wheel, on the front fork or rear swingarm.
- Brake fluid reservoir/master cylinder: at the handlebar for the front brake; near the rear pedal if separate.
- CVT: large casing on the left side of the rear wheel on scooters.
- Radiator cap: on top of the radiator, often behind the front panel.
- Coolant reservoir: behind the front panel or near the engine, depending on the model.
- Throttle body/injector: under the seat/airbox, on the intake side of the engine.
- Headlight bulb: inside the headlight housing, behind the rear connector.
- Tail light: rear fender/body panel.
- Sidestand switch: at the sidestand pivot.
- Clutch: right side of the engine on manual bikes; scooters use a CVT instead.

{convo_history_str}
## CURRENT USER MESSAGE
User: {message}

Your response as J.A.R.V.I.S.:"""

    try:
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=full_prompt,
            config=types.GenerateContentConfig(temperature=0.7),
        )
        reply_text = response.text
        if reply_text:
            _save_offline_knowledge(message, reply_text)
            try:
                from apps.core.models import GeminiUsageTracker
                meta = getattr(response, 'usage_metadata', None)
                p_tokens = getattr(meta, 'prompt_token_count', 0) or 0
                c_tokens = getattr(meta, 'candidates_token_count', 0) or 0
                GeminiUsageTracker.record_usage(prompt_tokens=p_tokens, candidates_tokens=c_tokens)
            except Exception:
                pass
        return reply_text
    except Exception as exc:
        logger.warning('General Gemini call failed; using offline fallback: %s', exc)
        return None


def _jarvis_gemini(message, user, history=None, mode='diagnostic', language=None):
    """
    Calls Gemini AI with full multi-turn conversational vehicle diagnostic mechanic system.
    """
    if mode == 'general':
        return _jarvis_gemini_general(message, user, history=history, language=language)

    client = _get_gemini_client()
    if client is None:
        return None

    from apps.motor.models import DiagnosticSymptom, Part, TroubleshootingGuide

    symptoms = DiagnosticSymptom.objects.prefetch_related(
        'troubleshooting_guides__required_parts__part'
    ).all()[:30]

    knowledge_lines = []
    for symptom in symptoms:
        knowledge_lines.append(f"\n### Symptom: {symptom.symptom_name} (Category: {symptom.category})")
        if symptom.description:
            knowledge_lines.append(f"Description: {symptom.description}")
        for guide in symptom.troubleshooting_guides.all()[:3]:
            knowledge_lines.append(f"  Possible Cause: {guide.possible_cause}")
            knowledge_lines.append(f"  Repair Instructions: {guide.repair_instructions[:300]}")
            if guide.advice_notes:
                knowledge_lines.append(f"  Advice: {guide.advice_notes}")
            parts = guide.required_parts.all()
            if parts:
                parts_str = ', '.join(
                    f"{rp.part.part_name} x{rp.quantity_needed}" for rp in parts
                )
                knowledge_lines.append(f"  Required Parts: {parts_str}")

    parts_catalogue = Part.objects.all()[:30]
    parts_lines = []
    for part in parts_catalogue:
        parts_lines.append(
            f"- {part.part_name} | Part#: {part.part_number or 'N/A'} | "
            f"Category: {part.category or 'General'} | Cost: ${part.estimated_cost}"
        )

    sir = _jarvis_address(user)

    convo_history_str = ""
    if history and isinstance(history, list):
        formatted_turns = []
        for turn in history[-16:]:
            r = "User" if turn.get('role') == 'user' else "J.A.R.V.I.S."
            txt = turn.get('text', '').strip()
            txt = re.sub(r'\[chips:.*?\]', '', txt).strip()
            if txt:
                formatted_turns.append(f"{r}: {txt}")
        if formatted_turns:
            convo_history_str = (
                "\n## PREVIOUS CONVERSATION TURNS (Analyze this entire session holistically — maintain continuity and DO NOT re-ask answered questions):\n"
                + "\n".join(formatted_turns)
                + "\n"
            )

    # Detect/normalise language for diagnostic prompt
    if not language or language not in ('english', 'tagalog', 'hiligaynon'):
        language = _detect_language(message, history)
    _DLANG_LABELS = {
        'english': 'English',
        'tagalog': 'Filipino / Tagalog',
        'hiligaynon': 'Hiligaynon / Ilonggo',
    }
    dlang_label = _DLANG_LABELS.get(language, 'English')

    full_prompt = f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the master vehicle diagnostic mechanic and repair assistant for an automotive and motorcycle workshop. You diagnose motorcycles, scooters, underbones, tricycles, cars, SUVs, and light trucks. You speak like Tony Stark's assistant: professional, courteous, precise, witty, and prioritizing safety above all else. Address the user respectfully as '{sir}'.

## MANDATORY LANGUAGE INSTRUCTION
DETECTED LANGUAGE: {dlang_label} ({language})
YOU MUST RESPOND ENTIRELY IN {dlang_label.upper()}. This is non-negotiable. Keep technical part names (caliper, CVT, spark plug, ECU) in their original English form.

You have access to the workshop diagnostic database:

## WORKSHOP DIAGNOSTIC DATABASE
{"".join(knowledge_lines) if knowledge_lines else "No symptoms on file yet."}

## WORKSHOP PARTS INVENTORY
{chr(10).join(parts_lines) if parts_lines else "No parts catalogued yet."}

## 1. CRITICAL MANDATE — HELP FIRST BEFORE RECOMMENDING A MECHANIC
- ALWAYS try to actively help the user troubleshoot and diagnose the issue first!
- NEVER immediately tell the user to go to a mechanic or tow the vehicle right away without attempting diagnosis.
- Walk the user through safe, actionable DIY inspections (checking fluid level, reservoir sight glass, pad thickness, battery terminals, fuses, spark).
- Suggest visiting a qualified mechanic ONLY if guided checks fail to resolve the problem, if severe irreversible damage is confirmed, or if specialized workshop machinery is strictly necessary.
- NEVER state "I am afraid this is outside my diagnostic database" or give a vague brush-off.

## 2. KEEP RESPONSES SHORT & CONCISE (DO NOT OVERWHELM THE USER)
- When vehicle intake is required, keep your accompanying text SHORT, courteous, and direct (2 to 4 sentences).
- DO NOT output a long wall of numbered questions in your text if the vehicle intake form is being displayed — the interactive form already collects those details!
- State that you are ready to help them diagnose the issue first, include any essential safety rule, ask them to confirm their vehicle make, model, year, and symptom in the form below, and emit the tag:
  `[vehicle-form: {{"category": "start"}}]` (or `brake`, `overheat`, `accel`, `general`)
  followed by 3 to 5 matching action chips.
- MEMORY RULE: If the user has ALREADY provided any vehicle detail, NEVER ask for it again! Automatically reuse known details.

## 3. PROBLEM-SPECIFIC DIAGNOSTIC RULES
- BRAKES: Warn never to test faulty brakes in traffic. Guide user to inspect fluid level in master cylinder reservoir, bleeder nipple, and pad friction material before concluding the vehicle must be towed.
- ENGINE WILL NOT START: Isolate starter solenoid relay clicking vs slow crank vs normal crank with no spark/fuel vs completely dead electrical.
- ENGINE OVERHEATING: Warn never to open a hot radiator cap (scald risk). Check coolant level when cool, radiator fins, and electric fan operation.
- ACCELERATION / TRANSMISSION: Differentiate slipping CVT/clutch from fuel bogging/hesitation.
  * Ask vehicle make/model/year/engine size.
  * Ask starter behavior: A. completely dead/no lights, B. rapid clicking from relay, C. cranks slowly, D. cranks normally but no combustion, E. starts and dies immediately, F. engine locked/stuck.
  * Ask if fuel-injected or carbureted, battery condition/warning lights, fuel smell, or smoke.
  * Systematically narrow down: Battery/solenoid, starter motor, fuel delivery/pump, spark/ignition, compression, kill switch / sidestand sensor. Never claim the engine needs total replacement without evidence.
- ENGINE OVERHEATING:
  * Ask make/model/year; liquid-cooled vs air-cooled; when overheating occurs (idle/traffic vs highway/speed); coolant level; radiator fan running; steam or sweet smell.
  * MANDATORY SAFETY RULE: "SAFETY WARNING: Never open a hot radiator cap. Scald danger from boiling pressurized coolant. Allow the engine to cool down completely (at least 30-45 minutes) before inspecting."
  * Distinguish liquid vs air-cooled engines.
- ACCELERATION / TRANSMISSION / SLIPPING:
  * Ask make/model/year; does engine rev up without moving (clutch slipping / CVT belt or roller wear) vs engine sputtering, hesitating, or bogging down (fuel delivery, clogged jets, spark plug, air intake, restricted exhaust).
- ENGINE NOISES & VIBRATION:
  * Localize noise: top-end ticking (valve clearance), bottom-end knocking (rod/crank bearing — warn to shut off immediately!), side-casing rattling (cam chain tensioner / clutch basket), squealing (drive belt).
- OTHER SYSTEMS:
  * Electrical, charging, battery, tires, suspension, steering, oil/fluid leaks, smoke color (blue=oil, black=rich fuel, white=coolant/head gasket).

## 4. CONVERSATIONAL DIAGNOSTIC WORKFLOW (7 STEPS)
- Step 1: Understand the complaint.
- Step 2: Check available information from the current message and previous conversation history.
- Step 3: Ask targeted questions (2–5 at a time) formatted clearly with numbers (1, 2, 3...) and multiple choice letters (- A., - B., - C....).
- Step 4 & 5: Analyze answers and narrow down fault. When multiple causes exist, explain leading possibilities and suggest safe inspections to differentiate.
- Step 6: Provide repair instructions once enough information is gathered:
  * State the Most Likely Cause and Confidence Level (High, Medium, Tentative).
  * Explain why the symptoms indicate this cause.
  * List Tools and Parts needed.
  * Emphasize Safety precautions.
  * Provide step-by-step repair/inspection instructions formatted as an interactive checklist: `- [ ] 1. Step description`.
  * Explain how to verify the repair safely.
  * Advise when professional shop service is necessary.
- Step 7: Continue the conversation after checks/repairs — ask the user what they found.

## 4a. MANDATORY HOLISTIC SESSION ANALYSIS & CONTINUITY (CRITICAL)
- TREAT CONVERSATION AS A CONTINUOUS SESSION: Always analyze the entire conversation history before deciding what to say.
- PERSIST ON ACTIVE PROBLEM: If an issue or fault was discussed in earlier turns and the user has NOT explicitly confirmed it is fixed (e.g. 'it worked', 'fixed', 'ok na', 'naayos na') and has not asked to reset or start over, DO NOT abandon it! DO NOT ask a new question about what to fix now. Maintain focus on resolving that active issue.
- IF PREVIOUS STEP OR TEST FAILED: If the user indicates that a previous check or repair did not work ('didn\'t work', 'still not fixed', 'hindi gumana', 'ayaw pa rin'), acknowledge it directly and provide the next diagnostic test or secondary cause. DO NOT ask what vehicle problem they have!

## 4b. STEP-BY-STEP PROCEDURE EXECUTION MANDATE (CRITICAL)
- When you ask or offer to commence the step-by-step procedure (e.g. "commence the step-by-step procedure", "troubleshoot step-by-step"), OR when a procedure checklist (`- [ ]`) has been offered:
  * If the user responds with agreement or confirmation (e.g. "yes", "proceed", "start", "commence", "begin", "continue", "next step", "step 1", "ok", "ready", "sige", "umpisahan"):
    1. DO NOT stop, halt, or ask a brand-new symptom question!
    2. IMMEDIATELY deliver **Step 1** (or the next uncompleted step) with full details:
       - Clear, actionable instructions for that specific step.
       - Required tools/supplies for this step.
       - What exact reading, sound, or visual sign to look for (expected benchmark).
       - What to do if the result is abnormal.
       - A direct question asking what the user observed from performing this step.
       - Clickable action chips: `[chips: Step 1 passed (normal) | Step 1 failed (abnormal) | Need help with Step 1 | Show next step | It worked]`.

## 5. MULTILINGUAL SUPPORT (TAGALOG & HILIGAYNON)
- Fluently understand and respond in English, Tagalog / Filipino / Taglish, and Hiligaynon (Ilonggo).
- ALWAYS respond in the SAME language or dialect used by the user:
  * If the user speaks in Hiligaynon (e.g., "Maayong adlaw", "preno ko guba", "indi mag-andar", "nagasiga ang temperature", "nagapiti-piti ang tambutso"), answer fluently and naturally in Hiligaynon with polite mechanic tone ("sir" / "bossing"), using natural local terms (preno, disc brake, drum brake, tambutso, makina, spark plug, langis, kadena, baterya).
  * If the user speaks in Tagalog / Taglish (e.g., "Kamusta", "ayaw mag-start ng motor ko", "malambot ang preno", "umuusok"), reply in natural Tagalog/Taglish.
  * If the user speaks in English, reply in English.

## 6. INTERACTIVE ACTION CHIPS
- Conclude EVERY response with 3 to 5 clickable action chips matching the most relevant choices or answers in this exact format:
  `[chips: Option 1 | Option 2 | Option 3 | Option 4]`

## 7. PART VISUAL REFERENCE — "What is X?" & PICTURE QUERIES
- MANDATORY VISUAL CAPABILITY: You HAVE direct visual rendering capabilities in the user's interface using the tag: `[part-image: URL | Part Name]`.
  ABSOLUTELY NEVER say "as an AI, I cannot transmit live images directly", "I cannot provide pictures", "I do not have visual capabilities", or similar disclaimers. Always emit the `[part-image: URL | Part Name]` tag!
- When the user asks "What is a [part]?", "Show me a [part]", "What does a [part] look like?", or asks for a picture of a component, provide:
  1. A clear explanation of what the part is and what it does.
  2. A `[part-image: IMAGE_URL | Part Name]` tag using the correct Wikimedia Commons URL below.
  3. Key diagnostic signs or inspection tips for that part.
  4. NEVER show a vehicle-form or say you prepared an intake form when answering "what is X" or picture requests.
  5. NEVER say "I don't know" for these common parts — use the visual reference library below.

- Use these EXACT image URLs (Wikimedia Commons, reliable):
  - Brake Caliper: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Disc_brake_dba.jpg/480px-Disc_brake_dba.jpg | Brake Caliper]`
  - Brake Pad: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Brake_disc_and_pads.jpg/480px-Brake_disc_and_pads.jpg | Brake Pads & Disc]`
  - Disc Brake: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Disk_brake_dsc03270.jpg/480px-Disk_brake_dsc03270.jpg | Disc Brake System]`
  - Sprocket: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Sprocket_stars.jpg/480px-Sprocket_stars.jpg | Drive Sprocket]`
  - Drive Chain: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/A_drive_chain.jpg/480px-A_drive_chain.jpg | Motorcycle Drive Chain]`
  - Spark Plug: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Spark_plug_comparison.jpg/480px-Spark_plug_comparison.jpg | Spark Plug]`
  - Carburetor: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Carburetor_of_a_scooter.jpg/480px-Carburetor_of_a_scooter.jpg | Carburetor]`
  - Battery: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Yuasa_YTX12-BS.jpg/480px-Yuasa_YTX12-BS.jpg | Motorcycle Battery]`
  - Radiator: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Radiator-overflow.jpg/480px-Radiator-overflow.jpg | Radiator]`
  - Piston: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/4-Stroke-Engine.gif/240px-4-Stroke-Engine.gif | Engine Piston]`
  - Headlight / Headlamp: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Honda_Click_150i_V3.jpg/480px-Honda_Click_150i_V3.jpg | Motorcycle Headlight]`
  - Honda Click Headlight: `[part-image: https://thumb.wikimedia.org/wikipedia/commons/thumb/8/8c/2022_Honda_Click_160_ABS.jpg/500px-2022_Honda_Click_160_ABS.jpg | Honda Click Headlight]`
  - Tail Light: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Motorcycle_tail_light.jpg/480px-Motorcycle_tail_light.jpg | Motorcycle Tail Light]`
  - Starter Motor: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Starter_motor.jpg/480px-Starter_motor.jpg | Starter Motor]`
  - CVT (Continuously Variable Transmission): `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Variator_and_belt.jpg/480px-Variator_and_belt.jpg | CVT Variator & Belt]`
  - Shock Absorber: `[part-image: https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a4/Mini_Shocks.JPG/500px-Mini_Shocks.JPG | Shock Absorber]`
  - Front Fork: `[part-image: https://upload.wikimedia.org/wikipedia/commons/8/8b/Bmw-telescopic.jpg | Motorcycle Front Fork]`
  - Air Filter: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Air_filter_element.jpg/480px-Air_filter_element.jpg | Air Filter Element]`
  - Oil Filter: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Oil_filter_cutaway.jpg/480px-Oil_filter_cutaway.jpg | Oil Filter Cutaway]`
  - Fuel Injector: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Fuel_injector.jpg/480px-Fuel_injector.jpg | Fuel Injector]`
  - Throttle Body: `[part-image: https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Throttle_body.jpg/480px-Throttle_body.jpg | Throttle Body]`

## 8. NO VOLUNTARY OR ASSUMED SYMPTOMS (CRITICAL)
- NEVER invent, assume, or voluntarily draft troubleshooting for a symptom (such as assuming a "No-Start" condition) if the user has NOT reported a problem or breakdown!
- If the user mentions, inquires about, or switches to a vehicle without stating a problem, answer any question they asked directly and courteously ask what symptom, mechanical issue, or routine service they need help with.
- When the user transitions from one vehicle to another, smoothly update focus without lecturing them about profile discrepancies.

## 9. NON-DIAGNOSTIC OR UNKNOWN COMPONENT QUERIES
- When the user asks "what is [X]", asks for a picture of something, or asks about a fictional/joke component (e.g. flux capacitor, time warp drive), or something outside vehicle mechanics, DO NOT output a `[vehicle-form: ...]` tag!
- Only output `[vehicle-form: ...]` when diagnosing an actual mechanical trouble symptom (e.g. engine won't start, squealing brakes, overheating, transmission slipping).
- If you don't know the answer or the component does not exist on a motorcycle/vehicle, politely and wittily say so without asking for vehicle diagnostic intake.

{convo_history_str}
## CURRENT USER MESSAGE
User: {message}

Your response as J.A.R.V.I.S.:"""

    model = model_name()
    if not model:
        logger.warning('Legacy AI request skipped: no Gemini model is configured.')
        return None

    try:
        response = client.models.generate_content(model=model, contents=full_prompt)
    except Exception as exc:
        # Do not log provider text: it can contain request details or clues
        # about server credentials.  The exception type is enough for support.
        logger.warning('Legacy AI request failed (%s).', type(exc).__name__)
        fallback = fallback_model_name()
        if not fallback or fallback == model:
            return None
        try:
            response = client.models.generate_content(model=fallback, contents=full_prompt)
        except Exception as fallback_exc:
            logger.warning('Legacy AI fallback failed (%s).', type(fallback_exc).__name__)
            return None

    try:
        reply_text = response.text
    except Exception as exc:
        logger.warning('Legacy AI response was unreadable (%s).', type(exc).__name__)
        return None
    if reply_text:
        _save_offline_knowledge(message, reply_text)
        try:
            from apps.core.models import GeminiUsageTracker
            meta = getattr(response, 'usage_metadata', None)
            p_tokens = getattr(meta, 'prompt_token_count', 0) or 0
            c_tokens = getattr(meta, 'candidates_token_count', 0) or 0
            GeminiUsageTracker.record_usage(prompt_tokens=p_tokens, candidates_tokens=c_tokens)
        except Exception:
            pass
    return reply_text


# ---------------------------------------------------------------------------
# Part Visual Reference Library — "What is X?" / "Show me X" visual assets
# ---------------------------------------------------------------------------
PART_VISUAL_LIBRARY = {
    'caliper': (
        'Brake Caliper',
        'The **brake caliper** is a hydraulic clamp mounted over the brake rotor disc. '
        'When you squeeze the brake lever, pressurized brake fluid pushes pistons inside the caliper, '
        'squeezing the brake pads against both sides of the spinning rotor disc to slow the wheel. '
        'Most motorcycles use a single-piston sliding caliper on the front wheel.\n\n'
        '**Key parts inside a caliper:** Piston(s) · Piston seals · Dust boot · Bleeder nipple/screw · Caliper body · Pad retaining pins',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Disc_brake_dba.jpg/480px-Disc_brake_dba.jpg',
        'What is a brake disc rotor? | What is a brake pad? | Brake lever feels soft | How to bleed brakes',
    ),
    'disc brake': (
        'Disc Brake System',
        'A **disc brake** system uses a flat metal rotor (disc) attached to the wheel hub. '
        'The brake caliper squeezes brake pads onto both faces of the spinning rotor to generate stopping friction. '
        'Disc brakes are more effective than drum brakes and dissipate heat much faster, especially under heavy or repeated braking.\n\n'
        '**Main components:** Rotor disc · Caliper · Brake pads · Brake line · Master cylinder · Brake fluid (DOT 3 or DOT 4)',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Disk_brake_dsc03270.jpg/480px-Disk_brake_dsc03270.jpg',
        'What is a brake caliper? | What is a brake pad? | Brake lever feels soft | Squealing brake sound',
    ),
    'brake pad': (
        'Brake Pad',
        'A **brake pad** is a flat friction material block inside the caliper that presses against the rotor disc. '
        'It is made of metallic, semi-metallic, or organic compounds designed to withstand high heat while generating consistent stopping friction. '
        'Worn brake pads (under 2 mm remaining) cause squealing or grinding sounds and dramatically reduce stopping power.\n\n'
        '**Check:** Look at the pad thickness through the caliper inspection window. If the friction material is flush with or thinner than the metal backing plate, replace immediately.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Brake_disc_and_pads.jpg/480px-Brake_disc_and_pads.jpg',
        'What is a brake caliper? | What is a disc brake? | Squealing brake sound | Metal grinding when braking',
    ),
    'sprocket': (
        'Drive Sprocket',
        'A **sprocket** is a toothed metal gear wheel that meshes with a drive chain to transfer engine power to the rear wheel. '
        'Motorcycles have two: the **front countershaft sprocket** (smaller, attached to the gearbox output shaft) and the '
        '**rear sprocket** (larger, bolted to the rear wheel hub). As the engine turns, the chain rotates both sprockets, driving the rear wheel.\n\n'
        '**Signs of worn sprockets:** Hooked or shark-fin shaped teeth · Chain jumping or skipping · Excessive chain slack · Visible metal wear on tooth tips.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Sprocket_stars.jpg/480px-Sprocket_stars.jpg',
        'What is a drive chain? | Chain & sprocket replacement | Smoke near engine casing & sprocket | Strange engine noise',
    ),
    'drive chain': (
        'Motorcycle Drive Chain',
        'The **drive chain** (or roller chain) is a series of metal links that connects the front sprocket to the rear sprocket, '
        'transferring engine torque to the rear wheel. It must be kept at the correct tension and well-lubricated for reliable power delivery and long life.\n\n'
        '**Inspection checklist:**\n'
        '- Slack: 20–30 mm free play at the midpoint (check owner\'s manual)\n'
        '- Lubricate every 500 km with dedicated chain lube (not WD-40)\n'
        '- Replace if any link is stiff, rusted, kinked, or if sprocket teeth are hooked.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/A_drive_chain.jpg/480px-A_drive_chain.jpg',
        'What is a sprocket? | Chain tension adjustment | Smoke near engine casing & sprocket | Strange engine noise',
    ),
    'spark plug': (
        'Spark Plug',
        'A **spark plug** screws into the cylinder head and fires a high-voltage electric spark (10,000–40,000 volts) '
        'that ignites the compressed air-fuel mixture inside the combustion chamber. '
        'It also acts as a "health report" for the engine — you can read combustion problems from the electrode color.\n\n'
        '**Reading spark plug color:**\n'
        '• **Light grey / tan** = Healthy combustion ✓\n'
        '• **Black & sooty** = Rich mixture or oil fouling\n'
        '• **White / blistered** = Lean mixture or overheating\n'
        '• **Wet & fuel-smelling** = Engine flooded',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Spark_plug_comparison.jpg/480px-Spark_plug_comparison.jpg',
        'Cranks normally but won\'t start | What is a carburetor? | Black smoke from exhaust | Engine overheating',
    ),
    'carburetor': (
        'Carburetor',
        'A **carburetor** (carb) is a mechanical device that mixes air and fuel in the correct ratio before it enters the engine. '
        'It uses venturi effect (air flowing through a narrow passage creates low pressure) to draw fuel from a float bowl and atomize it into fine droplets.\n\n'
        '**Key parts inside a carburetor:** Main jet · Pilot (idle) jet · Float & needle valve · Air/fuel mixture screw · Choke plate / enricher · Throttle slide or butterfly valve\n\n'
        '**Common problems:** Clogged jets (hard start, stalling), incorrect float height (rich/lean mixture), vacuum air leaks.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Carburetor_of_a_scooter.jpg/480px-Carburetor_of_a_scooter.jpg',
        'Cranks normally but won\'t start | What is a spark plug? | Engine won\'t accelerate properly | Black smoke from exhaust',
    ),
    'battery': (
        'Motorcycle Battery',
        'The **motorcycle battery** stores electrical energy to power the starter motor, ignition, lights, and instruments. '
        'Most modern motorcycles use a sealed **AGM (Absorbent Glass Mat)** or **Lithium-Ion (LiFePO4)** 12V battery.\n\n'
        '**Key voltages to know:**\n'
        '• **12.6–12.8V** = Fully charged and healthy\n'
        '• **12.0V** = ~50% discharged — recharge immediately\n'
        '• **Below 11.5V** = Battery damaged or deeply discharged\n'
        '• **During cranking: must stay above 9.6V** — if it drops lower, the battery is too weak to start the engine.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Yuasa_YTX12-BS.jpg/480px-Yuasa_YTX12-BS.jpg',
        'Rapid clicking when starting | Completely dead — no lights | Battery diagnostic | What is a starter motor?',
    ),
    'starter motor': (
        'Starter Motor',
        'The **starter motor** is a small but powerful electric motor that cranks (spins) the engine when you press the starter button. '
        'It draws 50–80 Amperes from the battery through the starter solenoid relay to turn the crankshaft and start combustion.\n\n'
        '**Signs of a failing starter motor:**\n'
        '• Grinding or whirring sound when pressing starter\n'
        '• Starter spins freely but doesn\'t engage engine (worn Bendix drive)\n'
        '• Tap starter casing with a plastic mallet — if it then turns, the carbon brushes are worn.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Starter_motor.jpg/480px-Starter_motor.jpg',
        'Rapid clicking when starting | Starter doesn\'t respond, lights work | What is a battery? | Starting failure scan',
    ),
    'cvt': (
        'CVT (Continuously Variable Transmission)',
        'A **CVT (Continuously Variable Transmission)** is the automatic gearbox system used in most scooters (Honda Click, Yamaha NMAX, Aerox, Mio). '
        'Instead of fixed gears, it uses a V-belt running between two variable-diameter pulleys — the **drive variator** (front) and **driven pulley** (rear). '
        'As engine speed increases, centrifugal flyball rollers push the front pulley wider, changing the belt ratio smoothly and automatically.\n\n'
        '**Key wear items:** Drive belt (V-belt) · Flyball rollers (variator weights) · Driven pulley spring · Clutch shoes',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Variator_and_belt.jpg/480px-Variator_and_belt.jpg',
        'Engine revs high but won\'t speed up | What is a clutch? | Motorcycle won\'t accelerate properly | Strange engine noise',
    ),
    'radiator': (
        'Radiator (Cooling System)',
        'The **radiator** is the heat exchanger that cools the engine coolant by passing air through its aluminum fin-and-tube matrix. '
        'Hot coolant from the engine water jacket flows through the radiator tubes; the thin aluminum fins dissipate heat to the passing air. '
        'An electric **radiator fan** turns on automatically when coolant temperature reaches ~95°C at idle or in traffic.\n\n'
        '**SAFETY WARNING:** Never open a hot radiator cap! Pressurized boiling coolant can cause severe scald burns. Allow the engine to cool 30–45 minutes.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Radiator-overflow.jpg/480px-Radiator-overflow.jpg',
        'Engine overheating | Radiator fan not spinning | Coolant leaking | White smoke from exhaust',
    ),
    'piston': (
        'Engine Piston',
        'The **piston** is a cylindrical metal component that moves up and down inside the engine cylinder. '
        'On the compression stroke it compresses the air-fuel mixture; on the power stroke the ignited explosion pushes the piston down, '
        'turning the crankshaft. The piston is sealed against the cylinder wall by **piston rings** (compression rings and oil scraper rings).\n\n'
        '**Signs of worn pistons/rings:** Blue oily smoke · Low compression reading · Excessive oil consumption · Engine noises.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/4-Stroke-Engine.gif/240px-4-Stroke-Engine.gif',
        'Blue smoke from exhaust | Low compression symptoms | Engine overhaul | What is a spark plug?',
    ),
    'headlight': (
        'Motorcycle Headlight',
        'The **headlight** is the primary forward-facing lighting system on a motorcycle or scooter. '
        'Modern bikes use **LED** (Light Emitting Diode) or **halogen** bulb technology. '
        'The headlight assembly typically contains the main beam, low/high beam reflector, '
        'and in newer models integrated **DRL (Daytime Running Lights)** and LED position lamps.\n\n'
        '**Common headlight issues:**\n'
        '• Bulb burned out → H4, HS1, or LED module replacement\n'
        '• Headlight not turning on → check fuse #5 or headlight relay\n'
        '• Flickering → loose bulb socket or failing charging system (stator)\n'
        '• Dim light → corroded ground wire or voltage regulator fault',
        'https://thumb.wikimedia.org/wikipedia/commons/thumb/8/84/Scooter_headlights.jpg/500px-Scooter_headlights.jpg',
        'What is a tail light? | Headlight not working | Electrical system check | What is a stator?',
    ),
    'tail light': (
        'Motorcycle Tail Light / Brake Light',
        'The **tail light** (or rear lamp) is the red-lens light assembly at the rear of the motorcycle. '
        'It serves two functions:\n'
        '• **Tail light** — stays on at low brightness whenever ignition is ON\n'
        '• **Brake light** — activates at full brightness when front or rear brake is applied\n\n'
        'Most modern motorcycles use **LED** tail lights for instant response and long life.\n\n'
        '**Common issues:** Bulb burned out (replace with equivalent T20 or LED) · '
        'Brake light not activating → faulty brake light switch on lever or pedal · '
        'Water ingress causing corrosion in bulb socket.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Motorcycle_tail_light.jpg/480px-Motorcycle_tail_light.jpg',
        'What is a headlight? | Electrical system check | What is a brake switch?',
    ),
    'air filter': (
        'Air Filter (Engine Air Cleaner)',
        'The **air filter** (air cleaner element) removes dust, sand, and airborne particles from intake air '
        'before it enters the carburetor or throttle body. A clean air filter ensures the correct air-fuel ratio for efficient combustion.\n\n'
        '**Types:** Paper/pleated element (dry) · Foam element (oiled, washable) · Cotton gauze (performance)\n\n'
        '**Symptoms of a clogged air filter:**\n'
        '• Black sooty exhaust smoke\n'
        '• Hard starting or rough idle\n'
        '• Reduced acceleration and fuel economy\n'
        '• Rich fuel smell at exhaust\n\n'
        '**Service interval:** Inspect every 4,000 km; replace every 8,000–12,000 km or sooner in dusty conditions.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Air_filter_element.jpg/480px-Air_filter_element.jpg',
        'Motorcycle won\'t accelerate properly | Black smoke from exhaust | What is a carburetor? | Engine oil change',
    ),
    'oil filter': (
        'Oil Filter',
        'The **oil filter** is a cartridge or spin-on canister that removes metallic particles, combustion carbon, '
        'and dirt from the engine oil as it circulates. Keeping the oil clean prevents premature wear of bearings, pistons, and cylinder walls.\n\n'
        '**Types:** Spin-on canister (common on larger bikes) · Cartridge/paper element (most scooters & underbones)\n\n'
        '**Replacement:** Always replace the oil filter at every engine oil change. '
        'Never re-use a filter — bypassed oil dumps particles directly onto engine bearings.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Oil_filter_cutaway.jpg/480px-Oil_filter_cutaway.jpg',
        'Engine oil change | What is engine oil? | Metallic ticking from top end | Engine noise diagnostic',
    ),
    'shock absorber': (
        'Shock Absorber (Rear Suspension)',
        'A **shock absorber** (damper) controls the rebound and compression of the suspension spring to keep the tire in contact with the road surface. '
        'Most scooters and underbones use **twin rear shock absorbers**, while sport bikes and nakeds use a **monoshock** with linkage.\n\n'
        '**Signs of worn shocks:**\n'
        '• Excessive bouncing after hitting a bump\n'
        '• Oil leaking from the shock body or seal\n'
        '• Bottoming out on moderate bumps\n'
        '• Vague or wallowing handling on corners',
        'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a4/Mini_Shocks.JPG/500px-Mini_Shocks.JPG',
        'Strange noise from suspension | Motorcycle handling problem | Front fork check | Tire inspection',
    ),
    'fuel injector': (
        'Fuel Injector (EFI System)',
        'A **fuel injector** is an electronically controlled solenoid valve that atomizes and sprays pressurized fuel '
        'directly into the intake port or throttle body in precise micro-bursts. '
        'The ECU (Engine Control Unit) controls the injector pulse width (milliseconds open) to achieve the correct air-fuel mixture at all rpm and load conditions.\n\n'
        '**EFI advantages over carburetor:** Better cold start · Precise fuel delivery at altitude · Lower emissions · Better fuel economy\n\n'
        '**Common injector problems:** Clogged nozzle (hard start, rough idle) · Leaking injector (rich mixture, fuel smell) · '
        'Failed injector (no start on that cylinder)',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Fuel_injector.jpg/480px-Fuel_injector.jpg',
        'Cranks normally but won\'t start | What is a carburetor? | Engine won\'t accelerate properly | Black smoke from exhaust',
    ),
    'throttle body': (
        'Throttle Body (EFI)',
        'The **throttle body** is the air metering device in a fuel-injected engine that controls how much air enters the intake manifold. '
        'When you twist the throttle grip, a cable or electronic signal opens the throttle plate (butterfly valve) inside the throttle body, '
        'allowing more air in. The ECU then commands the fuel injector to spray a matching amount of fuel.\n\n'
        '**Common throttle body issues:** Carbon deposits causing rough idle (clean with throttle body cleaner) · '
        'TPS (Throttle Position Sensor) failure causing jerky response · '
        'IACV (Idle Air Control Valve) sticking causing high or low idle.',
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Throttle_body.jpg/480px-Throttle_body.jpg',
        'Engine won\'t accelerate properly | Cranks normally but won\'t start | What is a fuel injector? | Rough idle',
    ),
    'fork': (
        'Front Fork (Telescopic Fork)',
        'The **front fork** is the telescopic suspension system that connects the front wheel axle to the steering head of the frame. '
        'Two fork legs slide up and down on internal springs and hydraulic damping oil to absorb road bumps.\n\n'
        '**Signs of worn or leaking forks:**\n'
        '• Oil ring/stain around the inner tube above the fork seal\n'
        '• Soft or springy front end with little damping\n'
        '• Clunking or knocking noise over bumps\n'
        '• Uneven fork leg travel (one side lower than the other)',
        'https://upload.wikimedia.org/wikipedia/commons/8/8b/Bmw-telescopic.jpg',
        'What is a shock absorber? | Strange noise from suspension | Front brake not working | Tire inspection',
    ),
}


def _search_part_image(query):
    """
    Search Wikipedia for a real photo of any vehicle part or motorcycle model.
    Uses Wikipedia generator=search + pageimages API — fast, free, no API key required.
    Returns (image_url, page_title) or (None, None).
    """
    import urllib.request
    import urllib.parse
    import json

    headers = {'User-Agent': 'MotorAssistantAI/2.0 (motor-assistant-workshop; contact@motorassistant.local)'}

    clean_q = re.sub(r'[^a-zA-Z0-9\s]', ' ', query).strip()
    if not clean_q:
        return None, None

    candidates = [clean_q]
    if 'motorcycle' not in clean_q.lower() and 'scooter' not in clean_q.lower():
        candidates.append(f"{clean_q} motorcycle")

    for candidate in candidates:
        search_url = 'https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode({
            'action': 'query',
            'generator': 'search',
            'gsrsearch': candidate,
            'gsrlimit': '3',
            'prop': 'pageimages',
            'pithumbsize': 500,
            'format': 'json'
        })
        try:
            req = urllib.request.Request(search_url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                pages = data.get('query', {}).get('pages', {})
                for pid, p in sorted(pages.items(), key=lambda x: x[1].get('index', 99)):
                    thumb = p.get('thumbnail', {}).get('source')
                    if thumb:
                        return thumb, p.get('title', candidate)
        except Exception:
            pass

def _clean_wiki_url(url):
    """
    Cleans Wikipedia thumbnail URLs into direct, reliable CDN URLs.
    Strips tracking query strings and maps thumb.wikimedia.org to upload.wikimedia.org.
    """
    if not url:
        return url
    clean = url.split('?')[0].replace('thumb.wikimedia.org', 'upload.wikimedia.org')
    return clean


def _has_visual_intent(msg):
    """
    Returns True ONLY when the user explicitly requests to see an image/picture
    or asks what a specific component is.
    Returns False during diagnostic troubleshooting, repairs, or explanations.
    """
    m = msg.lower().strip()

    # Explicit visual nouns (e.g. "picture of caliper", "can you show photo of sprocket")
    visual_words = [
        r'\bpicture\b', r'\bpictures\b', r'\bphoto\b', r'\bphotos\b',
        r'\bimage\b', r'\bimages\b', r'\blarawan\b', r'\blitrato\b',
        r'\bhulagway\b', r'\blook like\b', r'\blooks like\b'
    ]
    if any(re.search(v, m) for v in visual_words):
        return True

    # "Show me" or "Show" followed by a component name, e.g. "show me headlight", "show me a caliper"
    if re.search(r'\bshow\b', m):
        # Exclude instructional actions like "show me how", "show me steps", "show me what to do"
        action_words = [r'\bhow\b', r'\bhow to\b', r'\bsteps?\b', r'\bwhat to do\b', r'\bwhere to\b', r'\bguide\b', r'\binstructions?\b', r'\bwhy\b']
        if not any(re.search(w, m) for w in action_words):
            return True

    # "What is X" component inquiries: "what is caliper", "what is a sprocket", "ano ang caliper"
    what_is_prefixes = [
        'what is a ', 'what is an ', 'what is ', 'what are ',
        'ano ang ', 'ano yung ', 'ano ba ang ', 'unsa ang ', 'unsa ini '
    ]
    if any(m.startswith(p) for p in what_is_prefixes):
        # Exclude diagnostic questions like "what is causing my overheat", "what is this sound"
        diagnostic_words = [r'\bwrong\b', r'\bcausing\b', r'\bissue\b', r'\bproblem\b', r'\bsymptom\b', r'\bbroken\b', r'\boverheat\b', r'\bsound\b', r'\bnoise\b', r'\bclicking\b', r'\bsmoke\b', r'\bleak\b', r'\bfault\b']
        if not any(re.search(dw, m) for dw in diagnostic_words):
            tagalog_prefix = any(m.startswith(p) for p in ['ano ang ', 'ano yung ', 'ano ba ang ', 'unsa ang ', 'unsa ini '])
            if tagalog_prefix:
                # "ano ang ..." is the general Tagalog/Hiligaynon "what is/what's" —
                # only treat it as a part-picture request when a picture is
                # explicitly asked for or a known part is named, otherwise
                # generic questions like "ano ang susunod?" get hijacked here.
                visual_noun = any(re.search(v, m) for v in [
                    r'\blarawan\b', r'\blitrato\b', r'\bhulagway\b', r'\bpicture\b', r'\bphoto\b', r'\bimage\b'
                ])
                known_part = any(k in m for k in PART_VISUAL_LIBRARY)
                return visual_noun or known_part
            return True

    return False


def _resolve_part_image(user_msg):
    """
    Given a user message with explicit visual intent, resolves the best (image_url, image_alt) pair.
    Only resolves when a motorcycle component is explicitly queried or when a specific part
    is being visually requested. NEVER attaches a whole vehicle photo during diagnostic troubleshooting.
    """
    m = user_msg.lower()
    VEHICLE_MODELS = [
        'honda click', 'yamaha nmax', 'yamaha aerox', 'yamaha mio', 'honda beat',
        'honda pcx', 'suzuki raider', 'kawasaki', 'honda tmx', 'honda xrm',
    ]
    specific_vehicle = next((v for v in VEHICLE_MODELS if v in m), None)

    # 1. Check known library
    for part_key, (title, desc, img_url, chips_str) in PART_VISUAL_LIBRARY.items():
        if part_key in m:
            if specific_vehicle:
                # Try specific model + part search first, e.g. "Honda Click headlight"
                live_img, live_title = _search_part_image(f"{specific_vehicle} {part_key}")
                if live_img:
                    return _clean_wiki_url(live_img), f"{title} — {specific_vehicle.title()}"
            return _clean_wiki_url(img_url), title

    # 2. Only if the user explicitly asked to see what a motorcycle itself looks like
    if specific_vehicle and any(kw in m for kw in ['show me a honda click', 'show me honda click', 'picture of honda click', 'photo of honda click', 'look like']):
        live_img, live_title = _search_part_image(specific_vehicle)
        if live_img:
            return _clean_wiki_url(live_img), specific_vehicle.title()

    # 3. For other motorcycle part keywords
    search_terms = [w for w in m.split() if len(w) > 3 and w not in {
        'what', 'show', 'tell', 'explain', 'does', 'look', 'like', 'the', 'this', 'that',
        'is', 'are', 'for', 'from', 'with', 'about', 'please', 'ang', 'ano', 'ito', 'yung',
        'unsa', 'ini', 'image', 'picture', 'photo', 'jarvis', 'sir', 'boss'
    }]
    if search_terms:
        live_img, live_title = _search_part_image(' '.join(search_terms[:3]))
        if live_img:
            return _clean_wiki_url(live_img), live_title or ' '.join(search_terms[:3]).title()

    return None, None


def _stem_token(word):
    """Light singular/plural normalization: strips one trailing 's' (but not 'ss').
    Both sides of the knowledge-cache comparison use this, so consistency —
    not linguistic correctness — is what matters."""
    if len(word) > 3 and word.endswith('s') and not word.endswith('ss'):
        return word[:-1]
    return word


def _normalize_tokens(text):
    """Extracts meaningful normalized lowercase words, excluding common stop words."""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    stop_words = {
        'what', 'is', 'the', 'a', 'an', 'how', 'do', 'does', 'can', 'my', 'to',
        'of', 'for', 'in', 'on', 'at', 'by', 'and', 'or', 'with', 'from', 'about',
        'why', 'when', 'where', 'who', 'tell', 'me', 'please', 'help', 'jarvis',
        'sir', 'there', 'this', 'that', 'are', 'was', 'were', 'will', 'would', 'should'
    }
    tokens = [_stem_token(w) for w in clean.split() if len(w) >= 3 and w not in stop_words]
    return tokens


FOLLOWUP_RE = re.compile(
    r'what (?:should|do) i (?:do|check|inspect|test)|what(?:\s|\')(?:s| is) (?:next|now|first)'
    r'|where do i start|and then\?*$|^ok$|^okay$|^go on$|^continue$'
    r'|ano(?:\s+ang)?\s+(?:susunod|sunod|next)|ano(?:\s+ng)?\s+(?:gagawin|gawin)|paano (?:po|ito|dito|ngayon)'
    r'|ano (?:ang )?buhaton|paano (?:ini|kini)|ano isunod'
)

TOPIC_KEYWORDS = [
    ('brake', ['brake', 'brakes', 'braking', 'preno', 'spongy', 'squeal', 'grinding', 'bleed']),
    ('start', ["won't start", 'wont start', 'not starting', 'starting problem', 'clicking',
               'crank', 'starter', 'no lights', 'ayaw mag-start', 'ayaw umandar',
               'indi mag-andar', 'lagatik']),
    ('smoke', ['smoke', 'usok', 'aso']),
    ('overheat', ['overheat', 'overheating', 'temperature', 'coolant', 'radiator',
                  'nag-iinit', 'uminit', 'nagasiga']),
    ('accel', ['accelerat', 'sluggish', 'sputter', 'bogs', 'revs high', 'slipping', 'clutch',
               'ayaw bumilis', 'hatak']),
    ('noise', ['noise', 'sound', 'knock', 'knocking', 'ticking', 'rattling', 'ingay', 'tunog']),
]

TOPIC_REDISPATCH_MSG = {
    'brake': 'brake problem',
    'start': "engine won't start",
    'smoke': 'smoke from exhaust',
    'overheat': 'engine overheating',
    'accel': 'acceleration problem',
    'noise': 'strange engine noise',
}


def _is_generic_followup(msg):
    """True when the message is a short generic prompt to continue the diagnosis."""
    return bool(FOLLOWUP_RE.search(msg))


def _last_diagnostic_topic(history):
    """Returns the most recent diagnostic topic mentioned in the conversation history.

    User turns are scanned newest-first; bot turns are only consulted when no
    user turn names a topic (bot chips echo many keywords at once).
    """
    if not history or not isinstance(history, list):
        return None
    recent = list(reversed(history[-8:]))
    user_texts = [(t.get('text', '') or '').lower() for t in recent if t.get('role') == 'user']
    all_texts = user_texts + [(t.get('text', '') or '').lower() for t in recent]
    for text in all_texts:
        if not text:
            continue
        for topic, keywords in TOPIC_KEYWORDS:
            if any(k in text for k in keywords):
                return topic
    return None


def _save_offline_knowledge(query, reply_text):
    """
    Saves or updates Gemini AI answers into the local JarvisKnowledge table.
    """
    if not query or not reply_text:
        return
    query_str = query.strip()
    tokens = _normalize_tokens(query_str)
    clean_query = ' '.join(tokens)

    # Skip generic chitchat from saving to technical cache
    skip_phrases = {'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'thanks', 'thank you', 'bye'}
    if query_str.lower() in skip_phrases or len(clean_query) < 3:
        return

    try:
        from apps.core.models import JarvisKnowledge

        keywords_str = ' '.join(sorted(set(tokens)))
        entry = JarvisKnowledge.objects.filter(clean_query=clean_query).first()
        if entry:
            entry.ai_response = reply_text
            entry.hit_count += 1
            entry.save(update_fields=['ai_response', 'hit_count', 'updated_at'])
        else:
            JarvisKnowledge.objects.create(
                user_query=query_str[:500],
                clean_query=clean_query[:500],
                keywords=keywords_str,
                ai_response=reply_text,
                source='gemini'
            )
    except Exception:
        pass


def _find_offline_knowledge(query, user):
    """
    Looks up previously saved Gemini knowledge from the local database when offline.
    """
    query_str = query.strip()
    query_tokens = set(_normalize_tokens(query_str))
    if not query_tokens:
        return None

    try:
        from apps.core.models import JarvisKnowledge

        clean_query = ' '.join(_normalize_tokens(query_str))
        # 1. Exact match on clean query
        exact = JarvisKnowledge.objects.filter(clean_query=clean_query).first()
        if exact:
            exact.hit_count += 1
            exact.save(update_fields=['hit_count', 'updated_at'])
            return exact.ai_response

        # 2. Keyword search across the whole cache: let the DB pre-filter rows
        # sharing any keyword substring, then score them in Python.
        keyword_q = Q()
        for t in query_tokens:
            keyword_q |= Q(keywords__contains=t)
        candidates = JarvisKnowledge.objects.filter(keyword_q)[:500]
        best_match = None
        best_score = 0.0

        for item in candidates:
            item_tokens = {_stem_token(t) for t in item.keywords.split()}
            if not item_tokens:
                continue
            common = query_tokens.intersection(item_tokens)
            if not common:
                continue
            score = len(common) / len(query_tokens)
            if score > best_score:
                best_score = score
                best_match = item

        # Require BOTH a strong query coverage and 2+ shared keywords so weak,
        # barely-related entries are not served as answers.
        if best_match:
            overlap_count = len(query_tokens.intersection({_stem_token(t) for t in best_match.keywords.split()}))
            if best_score >= 0.5 and overlap_count >= 2:
                best_match.hit_count += 1
                best_match.save(update_fields=['hit_count', 'updated_at'])
                return best_match.ai_response

    except Exception:
        pass

    return None


FORM_CATEGORY_HINTS = [
    ('start', ["won't start", 'wont start', 'not starting', 'starting problem', 'starting issue',
               'starter', 'crank', 'clicking', 'no lights', 'dead', 'ayaw mag-start',
               'ayaw umandar', 'indi mag-andar']),
    ('brake', ['brake', 'preno', 'lever soft', 'caliper']),
    ('overheat', ['overheat', 'radiator', 'coolant', 'temperature']),
    ('accel', ['accelerat', 'sputter', 'sluggish', 'clutch slip', 'revs high']),
]


def _fix_vehicle_form_category(reply, message):
    """Retags a generic [vehicle-form] category with the category hinted by the
    user's message — the model occasionally emits 'general' for clear complaints,
    which makes the intake form show the wrong symptom options."""
    m = re.search(r'\[vehicle-form:\s*\{[^}]*"category"\s*:\s*"([^"]+)"[^}]*\}\s*\]', reply)
    if not m or m.group(1) != 'general':
        return reply
    msg = message.lower()
    for category, keywords in FORM_CATEGORY_HINTS:
        if any(k in msg for k in keywords):
            return reply[:m.start()] + f'[vehicle-form: {{"category": "{category}"}}]' + reply[m.end():]
    return reply


def _jarvis_response(message, user, history=None, language=None, experience_level=None, guided_state=None):
    """
    Intelligent J.A.R.V.I.S. Multi-Turn Diagnostic Mechanic:
    1. Guided intake (web client only): identify motorcycle -> focus on it ->
       ask the problem -> show free "where to look" checks -> narrow -> verdict.
    2. Visual & Part Reference queries -> Instant visual card + description.
    3. Diagnostic & Troubleshooting -> orchestrate_diagnostic_response:
       - Critical safety alerts & stop-riding directives
       - Verified database knowledge retrieval (RAG)
       - Single targeted question selection (no bombardment)
       - Strict 9-point Step-by-Step Repair Tutor format
       - Multi-provider AI (Gemini, OpenAI-compatible)
       - Grounded local knowledge fallback (explicitly disclosed)
    4. Fallbacks: Offline Knowledge Cache & rule-based engine.

    `guided_state` is only passed by the HTTP endpoint (it lives in the user's
    session). Internal/direct callers pass None and keep the previous behaviour.
    """
    from .guided_diagnostic import is_general_motorcycle_query

    msg = message.lower().strip()
    is_general_query = is_general_motorcycle_query(message, history)
    # A maintenance/how-to question must not be mistaken for a request to see a
    # part picture, even if it starts with "what is ...".
    is_visual_query = _has_visual_intent(message) and not is_general_query

    # Guided narrowing flow (identify the bike first, then narrow the fault).
    if guided_state is not None:
        from .guided_diagnostic import handle_guided_turn, is_guided_intent
        if is_guided_intent(message, history, guided_state):
            lang = language or _detect_language(message, history)
            sir = _jarvis_address(user)
            return handle_guided_turn(
                message, user, history, guided_state, lang=lang, sir=sir
            )

    reply = None

    def _safe_call_gemini(fn, message, user, history=None, mode=None, language=None):
        try:
            kwargs = {}
            if mode is not None:
                kwargs['mode'] = mode
            if language is not None:
                kwargs['language'] = language
            return fn(message, user, history=history, **kwargs)
        except TypeError:
            try:
                if mode is not None:
                    return fn(message, user, history=history, mode=mode)
                return fn(message, user, history=history)
            except TypeError:
                return fn(message, user)

    if is_general_query:
        # Maintenance/how-to/service question: answer directly, no intake form.
        reply = _safe_call_gemini(_jarvis_gemini, message, user, history=history, mode='general', language=language or _detect_language(message, history))
        if not reply:
            reply = _find_offline_knowledge(message, user)
        if not reply:
            reply = _jarvis_general_fallback(
                message, user, history=history, language=language
            )
    elif is_visual_query:
        # Visual reference or "what is" query
        reply = _safe_call_gemini(_jarvis_gemini, message, user, history=history, language=language or _detect_language(message, history))
        if not reply:
            reply = _find_offline_knowledge(message, user)
        if not reply:
            reply = _jarvis_rule_based_diagnostic(message, user, history=history)
    else:
        # Diagnostic & repair queries
        try:
            from .diagnostic_engine import orchestrate_diagnostic_response
            reply = orchestrate_diagnostic_response(
                message, user, history=history, language=language, experience_level=experience_level,
                guided_state=guided_state
            )
        except Exception as e:
            reply = None

        if not reply:
            reply = _safe_call_gemini(_jarvis_gemini, message, user, history=history, language=language or _detect_language(message, history))
        if not reply:
            reply = _find_offline_knowledge(message, user)
        if not reply:
            reply = _jarvis_rule_based_diagnostic(message, user, history=history)

    if reply:
        reply = _fix_vehicle_form_category(reply, message)
        is_unknown_or_fictional = any(phr in reply.lower() for phr in [
            "no such thing", "fictional", "don't know", "cannot identify", "outside my", "not aware", "temporal displacement"
        ])

        # Strip vehicle-form if this was an informational/what-is/general query
        # or if the reply states it doesn't know / fictional item.
        if is_visual_query or is_general_query or is_unknown_or_fictional:
            reply = re.sub(r'\[vehicle-form:[^\]]+\]', '', reply).strip()
            # Clean robotic "as an AI I cannot transmit live images" disclaimers & accidental intake text
            reply = re.sub(r'I apologize,?\s*(?:sir;?\s*)?as an AI,?\s*I cannot (?:transmit|provide|display|send) (?:live )?images [^.]*\.\s*(?:However,\s*)?', '', reply, flags=re.IGNORECASE).strip()
            reply = re.sub(r'Since you are dealing with a critical safety component,?\s*I have prepared a quick intake form[^.]*\.', '', reply, flags=re.IGNORECASE).strip()
            reply = re.sub(r'I have prepared a quick intake form[^.]*\.', '', reply, flags=re.IGNORECASE).strip()

        # If user did NOT ask for a visual/picture, NEVER include a part image in diagnostic answers!
        if not is_visual_query:
            reply = re.sub(r'\[part-image:[^\]]+\]', '', reply).strip()
        elif not is_unknown_or_fictional and '[part-image:' not in reply:
            # User explicitly asked for a visual: resolve and attach image
            img_url, img_alt = _resolve_part_image(message)
            if img_url:
                chip_match = re.search(r'\[chips:', reply)
                img_tag = f"\n\n[part-image: {img_url} | {img_alt}]\n\n"
                if chip_match:
                    idx = chip_match.start()
                    reply = reply[:idx].rstrip() + img_tag + reply[idx:]
                else:
                    reply = reply.rstrip() + img_tag

        # The UI renders [chips: ...] as clickable actions; the model occasionally
        # omits them on short answers, so guarantee their presence — in the
        # language the user is speaking.
        if '[chips:' not in reply:
            lang = language if language in ('english', 'tagalog', 'hiligaynon') else _detect_language(message, history)
            if is_general_query:
                chips = FALLBACK_CHIPS['general'].get(lang, FALLBACK_CHIPS['general']['english'])
            elif is_visual_query:
                chips = FALLBACK_CHIPS['visual'].get(lang, FALLBACK_CHIPS['visual']['english'])
            else:
                chips = FALLBACK_CHIPS['diagnostic'].get(lang, FALLBACK_CHIPS['diagnostic']['english'])
            reply += f'\n\n[chips: {chips}]'

    return reply


def _jarvis_rule_based_diagnostic(message, user, history=None):
    """
    Intelligent offline diagnostic mechanic fallback engine:
    - Identifies vehicle first (brand, model, year, brake type, fuel system).
    - Asks problem-specific follow-up questions with multiple-choice letters.
    - Strictly enforces safety rules (brakes, overheating scald hazard, bottom-end knock).
    - Multilingual fluency: English, Tagalog, and Hiligaynon.
    - Checklists formatted as `- [ ] 1. ...` and interactive action chips.
    """
    from apps.motor.models import DiagnosticSymptom, Part, TroubleshootingGuide

    msg = message.lower().strip()
    sir = _jarvis_address(user)
    lang = _detect_language(message, history)
    veh = _extract_vehicle_info(message, history)

    has_vehicle = bool(veh['make'] or veh['model'])
    veh_label = " ".join(filter(None, [veh['year'], veh['make'], veh['model']])).strip()

    # ── Generic follow-up ("what should I check first?", "ano ang susunod?")
    # continues the most recent diagnostic topic from the conversation history ──
    if _is_generic_followup(msg):
        topic = _last_diagnostic_topic(history)
        if topic:
            msg = f"{TOPIC_REDISPATCH_MSG[topic]} {msg}"

    # ── Detect "What is X?" / "Show me X" / specific vehicle+part queries ──
    is_what_query = _has_visual_intent(message)

    if is_what_query:
        # Check known library or live search
        for part_key, (title, desc, img_url, chips_str) in PART_VISUAL_LIBRARY.items():
            if part_key in msg:
                resolved_img, resolved_title = _resolve_part_image(message)
                if resolved_img:
                    return (
                        f"**{resolved_title or title}** — Visual Reference, {sir}:\n\n"
                        f"{desc}\n\n"
                        f"[part-image: {resolved_img} | {resolved_title or title}]\n\n"
                        f"[chips: {chips_str}]"
                    )
                return (
                    f"**{title}** — Visual Reference, {sir}:\n\n"
                    f"{desc}\n\n"
                    f"[part-image: {img_url} | {title}]\n\n"
                    f"[chips: {chips_str}]"
                )

        # Not in library — try live search via _resolve_part_image
        resolved_img, resolved_title = _resolve_part_image(message)
        if resolved_img:
            return (
                f"**{resolved_title}** — Visual Reference, {sir}:\n\n"
                f"Here is a visual reference for **{resolved_title}**:\n\n"
                f"[part-image: {resolved_img} | {resolved_title}]\n\n"
                f"[chips: What is a caliper? | What is a sprocket? | What is a spark plug? | What is a headlight?]"
            )

        return (
            f"I couldn't find a photo for that specific part, {sir}. "
            "Try asking with the exact part name, for example:\n\n"
            "• *\"What is a headlight?\"*\n"
            "• *\"Show me a sprocket\"*\n"
            "• *\"What does a Honda Click headlight look like?\"*\n\n"
            "[chips: What is a caliper? | What is a sprocket? | What is a headlight? | What is a spark plug?]"
        )

    # Also detect direct image requests without "what is"
    for part_key, (title, desc, img_url, chips_str) in PART_VISUAL_LIBRARY.items():
        if part_key in msg and any(kw in msg for kw in ['image', 'picture', 'photo', 'diagram', 'larawan', 'litrato']):
            return (
                f"**{title}** — Visual Reference, {sir}:\n\n"
                f"{desc}\n\n"
                f"[part-image: {img_url} | {title}]\n\n"
                f"[chips: {chips_str}]"
            )

    # 4. Brake Diagnostic System (Intake -> Specific Questions -> Protocol)
    brake_trigger_re = r'\bbrak(?:e|es|ing|ed)\b|\bbreaks?\b|\bpreno(?:s)?\b|\bstopping\b|lever soft|pedal soft|\bpreho\b'
    if re.search(brake_trigger_re, msg) and 'list parts' not in msg and 'parts list' not in msg:
        # If vehicle is NOT identified yet, run intake & diagnostic questionnaire
        if not has_vehicle:
            if lang == 'hiligaynon':
                return (
                    f"Yari ako agud buligan ka mag-usisa kag mag-troubleshoot sang imo preno antes ka magkadto sa mekaniko, {sir}.\n\n"
                    "**PAHALIDLONG SA KALIGTASAN:** Indi gid pag-idrive ukon pag-testingan ang guba nga preno sa dalan. "
                    "Kon indi masarangan sang guided DIY checks ukon may grabe nga leak, ipaguyod ini sa mekaniko.\n\n"
                    "Palihog kumpirmaha ang brand/make, modelo, tuig (year), kag kon disc ukon drum brake sa madasig nga form sa idalom:\n\n"
                    '[vehicle-form: {"category": "brake"}]\n'
                    "[chips: 2022 Honda Click 125i Disc Brake - Humok ang lever | Drum brake - Maluya magkagat | Nagadul-ong ang lever | May nagatulo nga fluid]"
                )
            elif lang == 'tagalog':
                return (
                    f"Nandito ako para tulungan kang mag-troubleshoot at suriin ang preno bago magpasyang dalhin sa mekaniko, {sir}.\n\n"
                    "**BABALA SA KALIGTASAN:** Huwag munang gamitin o subukan ang may diperensyang preno sa kalsada. "
                    "Kung hindi maresolba sa guided inspection o may malalang tagas, ipahatak ito sa mekaniko.\n\n"
                    "Pakilagay ang brand/make, modelo, taon (year), at piliin kung disc o drum brake sa form sa ibaba:\n\n"
                    '[vehicle-form: {"category": "brake"}]\n'
                    "[chips: 2022 Honda Click 125i Disc Brake - Malambot ang lever | Drum brake - Mahina ang preno | Lumulubog ang lever | May tagas ng fluid]"
                )
            else:
                return (
                    f"At your service, {sir}. I am here to help you inspect and troubleshoot your brakes step-by-step before you consider taking it to a mechanic.\n\n"
                    "**SAFETY WARNING:** Do not ride or drive the vehicle until the brakes are fully restored and tested — never test faulty brakes in traffic. "
                    "If our guided checks cannot resolve the issue or if there is severe fluid leakage, we will have it safely transported to a qualified mechanic.\n\n"
                    "To pinpoint the exact steps for your disc brake or drum brake system, please enter your vehicle make, model, year, and symptom in the form below:\n\n"
                    '[vehicle-form: {"category": "brake"}]\n'
                    "[chips: 2022 Honda Click 125i Disc brake - Soft lever | Drum brake - Weak stopping | Lever goes all the way down | Fluid leak near caliper]"
                )

        # Vehicle IS known: Diagnose based on symptom details
        if any(k in msg for k in ['soft', 'spongy', 'mushy', 'all the way down', 'humok', 'malambot', 'lumubog', 'bleed', 'air']):
            localized = _localized_branch('brake_bleed', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Diagnostic confirmation for your **{veh_label}**, {sir}:\n\n"
                "**Most Likely Cause:** Air entrapment in hydraulic brake line or moisture-contaminated brake fluid (Confidence: High).\n"
                "**Why this occurs:** Air is compressible, absorbing hydraulic pressure when you squeeze the lever before fluid can force caliper pistons against the pads.\n\n"
                "**Required Tools & Materials:**\n"
                "- 8mm or 10mm box wrench\n"
                "- Fresh DOT 4 brake fluid (unopened bottle)\n"
                "- Clear 1/4-inch vinyl tubing & clean catch container\n"
                "- JIS / Phillips screwdriver & lint-free shop towels\n\n"
                "**Interactive Brake Bleeding Checklist:**\n"
                "- [ ] 1. Park vehicle on level ground and turn handlebars until master cylinder reservoir is perfectly horizontal.\n"
                "- [ ] 2. Wipe reservoir cap clean; remove 2 screws, cover, and rubber diaphragm.\n"
                "- [ ] 3. Inspect fluid level and color (dark amber or cloudy indicates moisture contamination).\n"
                "- [ ] 4. Slip 8mm box wrench over caliper bleeder nipple, then attach clear vinyl tubing routed into catch bottle.\n"
                "- [ ] 5. Top up reservoir to UPPER line with fresh DOT 4 fluid.\n"
                "- [ ] 6. Slowly pump brake lever 3 to 4 times, then hold squeezed firmly against handlebar grip.\n"
                "- [ ] 7. Crack bleeder nipple open 1/4 turn for 1 second; observe fluid and air bubbles in tubing, then snug nipple shut BEFORE releasing lever.\n"
                "- [ ] 8. Repeat pump-hold-bleed cycle until only clear fluid emerges with zero air bubbles.\n"
                "- [ ] 9. Verify lever resistance is firm and solid, top reservoir to upper level, and replace diaphragm/cap.\n\n"
                "**SAFETY ADVISORY:** Verify solid lever pressure for 60 seconds with vehicle stationary. If lever slowly sinks, inspect master cylinder piston cup seals or caliper piston seals.\n\n"
                "[chips: What brake fluid type? | How to inspect brake pads | Brake lever feels firm now | Check brake disc rotor]"
            )
        elif any(k in msg for k in ['squeak', 'squeal', 'chirp', 'high pitched', 'nagapiti', 'maingay']):
            localized = _localized_branch('brake_squeal', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Acoustic brake diagnosis for **{veh_label}**, {sir}.\n\n"
                "**Most Likely Cause:** Glazed brake pads or fine road dust accumulation between pads and rotor (Confidence: High).\n\n"
                "**Interactive Troubleshooting Checklist:**\n"
                "- [ ] 1. Remove caliper mounting bolts and slide caliper off brake rotor disc.\n"
                "- [ ] 2. Measure brake pad friction material thickness (replace if under 2.0 mm).\n"
                "- [ ] 3. Thoroughly spray rotor disc and caliper body with dedicated residue-free brake cleaner.\n"
                "- [ ] 4. Place 240-grit sandpaper on a flat surface; lightly scuff glazed shiny surface of brake pads in a figure-8 pattern.\n"
                "- [ ] 5. Apply a tiny smear of high-temp copper anti-seize paste to pad backing plate contact points (never on friction side).\n"
                "- [ ] 6. Reinstall caliper and torque mounting bolts to factory specification (25–30 Nm).\n\n"
                "[chips: Brake lever feels soft/spongy | Metal grinding sound | List all parts]"
            )
        elif any(k in msg for k in ['grind', 'grinding', 'metal on metal', 'kaskas']):
            localized = _localized_branch('brake_grinding', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"CRITICAL SAFETY WARNING, {sir}. **Severe Friction Material Exhaustion** on **{veh_label}**.\n\n"
                "The friction compound is completely worn away; the steel backing plate is grinding directly into the brake rotor disc.\n\n"
                "**Emergency Checklist:**\n"
                "- [ ] 1. Stop riding immediately — continued operation will score and destroy the rotor disc.\n"
                "- [ ] 2. Remove caliper retaining pins and extract worn brake pads.\n"
                "- [ ] 3. Inspect rotor surface for deep grooving or blue heat discoloration (replace rotor if thickness < 3.0mm).\n"
                "- [ ] 4. Clean caliper piston walls and gently push pistons back into caliper housing.\n"
                "- [ ] 5. Install fresh sintered or semi-metallic brake pads and secure retaining clips.\n\n"
                "[chips: Brake system check | List all parts | What tools do I need for this?]"
            )
        else:
            localized = _localized_branch('brake_generic_known', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Brake diagnostics engaged for **{veh_label}**, {sir}. What specific symptom is the brake exhibiting?\n\n"
                "[chips: Brake lever feels soft or spongy | Squeaking or high-pitched squeal | Metal grinding sound | Brake lever goes all the way down]"
            )

    # 5. Starting Failure Diagnostic System (Intake -> Specific Questions -> Protocol)
    starting_triggers = [
        "won't start", "wont start", "cant start", "cannot start", "doesn't start",
        "doesnt start", "not starting", "hard to start", "starting problem", "trouble starting",
        "starting issue", "no start", "fail to start", "fails to start", "starting failure scan",
        "ayaw mag-start", "ayaw umandar", "indi mag-andar", "indi magstart", "hindi mag-start"
    ]
    if any(k in msg for k in starting_triggers):
        if not has_vehicle:
            if lang == 'hiligaynon':
                return (
                    f"Yari ako agud buligan ka mag-usisa kon ngaa indi mag-andar ang imo salakyan antes ka magtawag sang mekaniko, {sir}.\n\n"
                    "Usisa-on naton ang baterya, starter, kuryente, kag gasolina sing pasunod. "
                    "Palihog kumpirmaha ang brand/make, modelo, tuig, kag kon nagalubid o naga-crank ang makina sa madasig nga form sa idalom:\n\n"
                    '[vehicle-form: {"category": "start"}]\n'
                    "[chips: May clicking sound sa relay | Nagalubid pero indi mag-andar | Mahinay mag-lubid | Patay tanan nga suga]"
                )
            elif lang == 'tagalog':
                return (
                    f"Nandito ako para tulungan kang hanapin ang diperensya kung bakit ayaw mag-start bago mo dalhin sa mekaniko, {sir}.\n\n"
                    "Susuriin natin ang baterya, starter, kuryente, at gasolina nang sunod-sunod. "
                    "Pakilagay ang brand/make, modelo, taon (year), at kung nagki-crank o umiikot ang makina sa form sa ibaba:\n\n"
                    '[vehicle-form: {"category": "start"}]\n'
                    "[chips: May clicking sound sa relay | Nagki-crank pero ayaw mag-start | Mabagal mag-crank | Walang kuryente o ilaw]"
                )
            else:
                return (
                    f"At your service, {sir}. I am here to help you troubleshoot why your vehicle will not start before you consider calling a mechanic.\n\n"
                    "We will systematically inspect your battery, starter motor, spark, and fuel delivery. "
                    "Please confirm your vehicle make, brand, or model, year, and whether the engine cranks or turns over when you press the starter in the form below:\n\n"
                    '[vehicle-form: {"category": "start"}]\n'
                    "[chips: Rapid clicking sound | Cranks normally, no combustion | Cranks slowly but won't start | Completely dead - no lights]"
                )

        # Vehicle IS known: ask symptom options if not yet provided
        localized = _localized_branch('start_known', lang, sir=sir, veh=veh_label)
        if localized:
            return localized
        return (
            f"Diagnostic protocol engaged for your **{veh_label}**, {sir}.\n\n"
            "To isolate the fault immediately, **what occurs when you press the starter?**\n\n"
            '[vehicle-form: {"category": "start"}]\n'
            "[chips: Rapid clicking sound | Cranks normally, no combustion | Cranks slowly but won't start | Completely dead - no lights]"
        )

    # Sub-branches for Starting Symptoms (clickable chips or direct text)
    if any(k in msg for k in ['rapid clicking', 'clicking sound', 'starter clicking', 'relay clicking', 'clicks but', 'clicking noise', 'lagatik']):
        localized = _localized_branch('start_clicking', lang, sir=sir, veh=veh_label)
        if localized:
            return localized
        return (
            f"Starting Diagnostic Analysis, {sir}. **Starter Solenoid Relay Chatter**.\n\n"
            "**Root Cause:** The battery maintains nominal surface voltage (12V) to close the relay coil, "
            "but when the starter motor draws 50–80 Amps, terminal voltage collapses below 10.5V. "
            "The coil releases, voltage rebounds, and cycles rapidly (clicking sound).\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Switch ignition OFF and inspect 10mm battery terminal bolts for loose fitment or white sulfate corrosion.\n"
            "- [ ] 2. Measure resting voltage with a multimeter (Healthy: 12.6V+; Discharged: < 12.0V).\n"
            "- [ ] 3. Measure battery terminal voltage while holding starter button (if it plunges below 9.6V, battery cells are degraded).\n"
            "- [ ] 4. Check negative ground cable bolted to engine casing for loose bolt or paint/corrosion.\n"
            "- [ ] 5. Connect a 12V motorcycle smart charger or test-jump with a healthy 12V battery.\n\n"
            "[chips: How to test battery with multimeter | Cranks slowly but won't start | Cranks normally, no combustion]"
        )

    if any(k in msg for k in ['cranks slowly', 'slow crank', 'cranking slow', 'turning slow', 'sluggish crank', 'mabagal mag-crank', 'mahinay mag-lubid']):
        localized = _localized_branch('start_slow_crank', lang, sir=sir, veh=veh_label)
        if localized:
            return localized
        return (
            f"Starting Diagnostic Analysis, {sir}. **High Electrical Drag or Depleted Battery Capacity**.\n\n"
            "**Root Cause:** The starter motor is receiving insufficient cranking amperage or fighting excessive mechanical resistance.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Check engine oil level and viscosity — cold or overfilled oil creates heavy drag.\n"
            "- [ ] 2. Inspect negative ground lead bolted to engine case for loose fastener or oxidation.\n"
            "- [ ] 3. Perform a voltage drop test across starter relay terminals during cranking (should be < 0.5V).\n"
            "- [ ] 4. Inspect starter motor carbon brushes for wear or oil penetration through the starter armature seal.\n\n"
            "[chips: Rapid clicking sound | Battery diagnostic | Engine oil check]"
        )

    if any(k in msg for k in ['cranks normally', 'no combustion', 'cranks but', 'wont fire', "won't fire", 'cranking fine', 'engine spins but', 'no spark']):
        localized = _localized_branch('start_no_combustion', lang, sir=sir, veh=veh_label)
        if localized:
            return localized
        return (
            f"Starting Diagnostic Analysis, {sir}. **Combustion Triangle Interruption**.\n\n"
            "The starter spins smoothly, ruling out battery and starter motor. The engine is missing either **Spark**, **Fuel**, or **Compression**.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Confirm handlebar kill switch is in 'RUN' position and side-stand is fully raised (safety interlock check).\n"
            "- [ ] 2. Remove spark plug; rest grounded metal threads against cylinder head and crank to inspect for crisp blue spark.\n"
            "- [ ] 3. Inspect spark plug tip: if wet and smelling of gas, engine is flooded; if bone dry, fuel delivery has stalled.\n"
            "- [ ] 4. For EFI models: turn key on and listen for high-pitch 2-second fuel pump priming buzz beneath fuel tank.\n"
            "- [ ] 5. For carburetor models: loosen float bowl drain screw to confirm clean fuel flows freely.\n\n"
            "[chips: How to test spark plug | Clean carburetor jets | Engine flooded protocol]"
        )

    if any(k in msg for k in ['completely dead', 'no lights', 'no power', 'no dash', 'nothing happens', 'no electric', 'patay lahat', 'patay tanan']):
        localized = _localized_branch('start_dead', lang, sir=sir, veh=veh_label)
        if localized:
            return localized
        return (
            f"Starting Diagnostic Analysis, {sir}. **Total Electrical Circuit Interruption**.\n\n"
            "**Root Cause:** Main electrical power is prevented from reaching the ignition switch and main fuse bus.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Check the Main 30A Fuse (housed inside or adjacent to the starter magnetic solenoid switch).\n"
            "- [ ] 2. Inspect battery terminal connections — clean lead posts and tighten 10mm terminal bolts.\n"
            "- [ ] 3. Inspect key ignition switch harness connector under the steering stem / fuel tank.\n"
            "- [ ] 4. Test battery terminal resting voltage with a multimeter — verify not reverse-connected or 0V.\n\n"
            "[chips: Where is the main fuse? | Rapid clicking sound | Check battery voltage]"
        )

    if any(k in msg for k in ['starts briefly', 'starts and dies', 'shuts off', 'dies immediately', 'namamatay agad', 'mapatay man gilayon']):
        localized = _localized_branch('start_dies', lang, sir=sir, veh=veh_label)
        if localized:
            return localized
        return (
            f"Starting Diagnostic Analysis, {sir}. **Combustion Sustenance Failure (Starts then Dies)**.\n\n"
            "**Root Cause:** The engine achieves initial ignition on cranking enrichment, but cannot sustain idle due to fuel starvation, unmetered air leak, or ignition drop.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. For EFI: Check fuel pump priming pressure and inspect fuel filter / injector spray pattern.\n"
            "- [ ] 2. For Carburetor: Clean pilot (idle) jet and adjust fuel/air mixture screw (typically 1.5 to 2 turns out).\n"
            "- [ ] 3. Inspect rubber intake manifold boot between throttle body/carburetor and cylinder head for vacuum cracks or loose clamps.\n"
            "- [ ] 4. Check Idle Air Control Valve (IACV) or manual idle stop screw setting.\n"
            "- [ ] 5. Test fuel quality — drain float bowl / tank sample to inspect for water contamination or stale fuel.\n\n"
            "[chips: Clean carburetor jets | Check fuel pump pressure | Test for vacuum leak]"
        )

    if any(k in msg for k in ['starter does not respond', 'starter not responding', 'lights work but no crank', 'dash lights on but', 'relay silent', 'indi mag-tiyog pero may suga']):
        localized = _localized_branch('start_silent', lang, sir=sir, veh=veh_label)
        if localized:
            return localized
        return (
            f"Starting Diagnostic Analysis, {sir}. **Starter Control Interlock Open Circuit**.\n\n"
            "**Root Cause:** The dashboard instruments receive 12V, but the starter relay control coil circuit remains open due to an active safety switch or broken control line.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Squeeze both brake levers firmly (scooters) or pull clutch lever (motorcycles) to ensure brake/clutch safety switch clicks.\n"
            "- [ ] 2. Inspect side-stand safety kill switch — clean road grime from the plunger spring mechanism.\n"
            "- [ ] 3. Disconnect handlebar starter button switch housing; spray contacts with electrical contact cleaner to remove oxidation.\n"
            "- [ ] 4. Locate starter solenoid relay and test for 12V signal on trigger wire when button is pressed.\n"
            "- [ ] 5. Tap starter motor casing lightly with a plastic mallet while pressing starter button (if it turns, starter carbon brushes are worn).\n\n"
            "[chips: Side stand switch test | Starter button cleaning | Rapid clicking sound]"
        )

    # 6. Overheating Diagnostic System (Intake -> Safety -> Protocol)
    overheat_triggers = ['overheating', 'overheat', 'temperature', 'radiator', 'coolant', 'nagasiga ang temperature', 'naga-overheat', 'nag-iinit', 'sobrang init']
    if any(k in msg for k in overheat_triggers):
        if not has_vehicle:
            if lang == 'hiligaynon':
                return (
                    f"Yari ako agud buligan ka mag-usisa sing hilway sang naga-overheat nga makina antes ka magkadto sa shop, {sir}.\n\n"
                    "**PAHALIDLONG SA KALIGTASAN:** Indi gid pag-buksi ang takop sang radiator samtang mainit pa ang makina! "
                    "Magasirit ang nagabukal nga coolant nga makatuga sang grabe nga paso. Palipasa anay ang 30-45 minutos tubtob magbugnaw.\n\n"
                    "Palihog kumpirmaha ang brand, modelo, tuig, kag sintomas sa madasig nga form sa idalom:\n\n"
                    '[vehicle-form: {"category": "overheat"}]\n'
                    "[chips: Nagasiga ang temperature light | Indi nagatuyok ang radiator fan | May nagatulo nga coolant | Air-cooled ang akon makina]"
                )
            elif lang == 'tagalog':
                return (
                    f"Nandito ako para tulungan kang ligtas na suriin ang overheating bago magpasyang dalhin sa talyer, {sir}.\n\n"
                    "**MAHIGPIT NA BABALA SA KALIGTASAN:** Huwag na huwag bubuksan ang takip ng radiator habang mainit pa ang makina! "
                    "Sasabog ang kumukulong coolant at singaw na maaaring magdulot ng matinding paso. Maghintay muna ng 30–45 minuto hanggang sa lumamig.\n\n"
                    "Pakilagay ang brand/make, modelo, taon, at sintomas sa form sa ibaba:\n\n"
                    '[vehicle-form: {"category": "overheat"}]\n'
                    "[chips: May warning light sa dashboard | Hindi umiikot ang radiator fan | May tumagas na coolant | Air-cooled ang aking motor]"
                )
            else:
                return (
                    f"At your service, {sir}. I am here to help you inspect and resolve the overheating safely before you need a shop.\n\n"
                    "**CRITICAL SAFETY WARNING:** Never open a hot radiator cap! Pressurized boiling coolant will erupt and cause severe scald burns. "
                    "Allow the engine to cool completely (30–45 minutes) before touch.\n\n"
                    "Please confirm your vehicle make, model, year, and overheating symptom in the form below:\n\n"
                    '[vehicle-form: {"category": "overheat"}]\n'
                    "[chips: Temperature light on | Radiator fan not spinning | Coolant boiling / leaking | Air-cooled motorcycle engine]"
                )

        # Vehicle IS known
        localized = _localized_branch('overheat_known', lang, sir=sir, veh=veh_label)
        if localized:
            return localized
        return (
            f"Cooling System Diagnostic Protocol for **{veh_label}**, {sir}:\n\n"
            "**CRITICAL SAFETY WARNING:** Never open a hot radiator cap. Allow the engine to cool down completely before touch.\n\n"
            "**Cooling System Inspection Checklist:**\n"
            "- [ ] 1. Allow engine to sit turned off for 45 minutes until radiator neck is cool to bare hands.\n"
            "- [ ] 2. Inspect coolant expansion reservoir level between MIN and MAX indicators.\n"
            "- [ ] 3. Remove radiator cap: check for milky oil residue (head gasket leak) or rust contamination.\n"
            "- [ ] 4. Inspect radiator aluminum cooling fins for road mud, crushed fins, or debris blockage.\n"
            "- [ ] 5. Start engine, allow temperature to reach 95°C–100°C: verify radiator electric fan turns on automatically.\n"
            "- [ ] 6. If fan does not spin: inspect fan relay, thermo-switch sensor, and cooling fan fuse.\n\n"
            "[chips: White sweet-smelling smoke | Engine oil check | Starting failure scan]"
        )

    # 7. Acceleration / Transmission / Slipping System
    accel_triggers = [
        'accelerat', 'acceleration', "won't accelerate", "wont accelerate", "loss of power",
        "sluggish", "hesitat", "bogs down", "sputter", "hindi bumibilis", "ayaw bumilis",
        "indi magbaskog", "buhin ang kadasigon", "clutch slip", "revs high"
    ]
    if any(k in msg for k in accel_triggers):
        if not has_vehicle:
            if lang == 'hiligaynon':
                return (
                    f"Yari ako agud buligan ka mag-usisa sang transmission kag hatak sang imo makina antes magkadto sa mekaniko, {sir}.\n\n"
                    "Usisa-on naton kon naga-slip ang clutch/CVT ukon nagapalpalyar sa gasolina ukon spark plug. "
                    "Palihog kumpirmaha ang brand, modelo, tuig, kag sintomas sa madasig nga form sa idalom:\n\n"
                    '[vehicle-form: {"category": "accel"}]\n'
                    "[chips: Naga-ugong pero indi magdasig | Nagapalpalyar kon biriton | Nadulaan kusog sa takas | Nagakurog sa arangkada]"
                )
            elif lang == 'tagalog':
                return (
                    f"Nandito ako para tulungan kang suriin ang arangkada at drivetrain bago dalhin sa mekaniko, {sir}.\n\n"
                    "Aalamin natin kung dumudulas ang clutch/CVT o pumapalya ang makina sa gasolina o spark. "
                    "Pakilagay ang brand/make, modelo, taon, at sintomas sa form sa ibaba:\n\n"
                    '[vehicle-form: {"category": "accel"}]\n'
                    "[chips: Umaatungal ang makina pero ayaw bumilis | Pumapalya kapag binibirit | Walang hatak sa ahon | Nanginginig sa arangkada]"
                )
            else:
                return (
                    f"At your service, {sir}. I am here to help you troubleshoot your drivetrain and acceleration before you decide to visit a mechanic.\n\n"
                    "We will isolate whether the engine is revving without speed (slipping clutch / CVT) or sputtering from fuel/ignition issues. "
                    "Please enter your vehicle make, model, year, and symptom in the form below:\n\n"
                    '[vehicle-form: {"category": "accel"}]\n'
                    "[chips: Engine revs high but won't speed up | Sputters and bogs on throttle | Sluggish on hills | Jerking at low speed]"
                )

        # Vehicle IS known
        if any(k in msg for k in ['revs high', 'slipping', 'clutch slip', 'umaatungal', 'naga-ugong']):
            localized = _localized_branch('accel_slip', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Drivetrain Analysis for **{veh_label}**, {sir}. **Transmission / Clutch Slip**.\n\n"
                "**Most Likely Cause:** Friction plates worn beyond service limit, incorrect clutch cable free play, or (on scooters) glazed CVT belt and worn flyball variator rollers.\n\n"
                "**Interactive Inspection Checklist:**\n"
                "- [ ] 1. Check clutch handlebar cable free play (ensure 2–3 mm free movement at perch).\n"
                "- [ ] 2. For scooters/CVT: remove crankcase belt cover; measure drive belt width with vernier caliper.\n"
                "- [ ] 3. Inspect variator rollers (flyballs) for flat spots or oval wear.\n"
                "- [ ] 4. For manual clutch: drain oil and inspect clutch friction disc thickness and pressure plate springs.\n"
                "- [ ] 5. Verify motorcycle oil used complies with JASO-MA2 standards (car oil with friction modifiers induces clutch slip).\n\n"
                "[chips: Engine oil check | Spark plug check | List all parts]"
            )
        else:
            localized = _localized_branch('accel_fuel', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Combustion & Fuel Analysis for **{veh_label}**, {sir}. **Fuel Starvation or Ignition Hesitation**.\n\n"
                "**Interactive Troubleshooting Checklist:**\n"
                "- [ ] 1. Remove and inspect air filter element for oil or dirt choking airflow.\n"
                "- [ ] 2. Inspect spark plug tip: clean electrode or replace if fouled or gap exceeds 0.8 mm.\n"
                "- [ ] 3. For EFI: clean fuel injector nozzle and inspect fuel pump delivery pressure.\n"
                "- [ ] 4. For carburetor: spray main jet and pilot jet with carb cleaner to clear varnish.\n\n"
                "[chips: Clean carburetor jets | Spark plug check | Air filter replacement]"
            )

    # 8. Acoustic / Engine Noise Diagnostic System
    noise_triggers = ['acoustic noise scan', 'noise', 'sound', 'knocking', 'ticking', 'rattling', 'slapping', 'clattering', 'ingay', 'tunog', 'lagatik', 'kumatok']
    if any(k in msg for k in noise_triggers):
        if any(k in msg for k in ['tick', 'ticking', 'tap', 'tapping', 'top end', 'valve', 'balbula']):
            localized = _localized_branch('noise_valve', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Acoustic analysis, {sir}. **Excessive Valve Tappet Clearance** in cylinder head.\n\n"
                "**Interactive Valve Adjustment Checklist:**\n"
                "- [ ] 1. Allow engine to cool completely (inspection must be performed at ambient room temp).\n"
                "- [ ] 2. Remove cylinder head valve inspection caps and alternator timing inspection plug.\n"
                "- [ ] 3. Rotate crankshaft with 14mm socket to Top Dead Center (TDC) on compression stroke (T mark aligned).\n"
                "- [ ] 4. Insert feeler gauge between rocker arm adjuster screw and valve stem tip.\n"
                "- [ ] 5. Loosen 9mm locknut, adjust screw until slight drag is felt on gauge, retighten locknut.\n\n"
                "[chips: Cam chain tensioner check | Oil pressure check | Strange engine noise]"
            )
        elif any(k in msg for k in ['knock', 'knocking', 'thud', 'bottom end', 'deep knock', 'kumatok']):
            localized = _localized_branch('noise_knock', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"URGENT CAUTION, {sir}. **Bottom-End Bearing Wear (Connecting Rod / Crank Journal)**.\n\n"
                "A heavy metallic thump synchronised with engine RPM that intensifies under throttle load indicates bearing play.\n\n"
                "**Inspection Protocol:**\n"
                "- [ ] 1. Shut off engine immediately to avoid catastrophic connecting rod ejection through engine crankcase.\n"
                "- [ ] 2. Drain engine oil into a clean pan; inspect for copper, brass, or silver metallic flakes.\n"
                "- [ ] 3. Inspect oil filter element for trapped metal shavings.\n"
                "- [ ] 4. Perform oil pressure test using a mechanical gauge attached to the main oil gallery port.\n\n"
                "[chips: Engine oil check | Metallic ticking from top end | List all parts]"
            )
        elif any(k in msg for k in ['rattle', 'rattling', 'slap', 'cam chain', 'timing chain']):
            localized = _localized_branch('noise_camchain', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Acoustic analysis, {sir}. **Loose Cam Timing Chain or Sticking Tensioner**.\n\n"
                "**Interactive Cam Chain Inspection Checklist:**\n"
                "- [ ] 1. Locate the automatic cam chain tensioner on the rear of the cylinder barrel.\n"
                "- [ ] 2. Remove center sealing bolt and spring to verify internal ratchet mechanism has not jammed.\n"
                "- [ ] 3. Manually turn tensioner screw clockwise to retract plunger, re-install, and release to reset tension.\n"
                "- [ ] 4. If noise persists, cam chain guide slippers or chain links are stretched beyond service limits.\n\n"
                "[chips: Metallic ticking from top end | Oil pressure check | Strange engine noise]"
            )
        else:
            localized = _localized_branch('noise_generic', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Acoustic scanner active, {sir}. Where is the mechanical noise localized?\n\n"
                "[chips: Metallic ticking from top end | Deep knocking from bottom end | Rattling / slapping from side casing | High-pitched squeal on acceleration]"
            )

    # 9. Smoke / Thermal Diagnostic Tree
    if any(k in msg for k in ['smoke', 'smoking', 'exhaust smoke', 'fumes']) or re.search(r'\b(?:usok|aso)\b', msg):
        if any(k in msg for k in ['blue', 'bluish', 'oil smoke']):
            localized = _localized_branch('smoke_blue', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Combustion thermal analysis, {sir}. **Engine Oil Entering Combustion Chamber**.\n\n"
                "**Root Cause:** Worn piston compression/oil scraper rings or hardened valve stem seals.\n\n"
                "**Interactive Compression Diagnostic Checklist:**\n"
                "- [ ] 1. Warm engine to operating temperature, then remove spark plug.\n"
                "- [ ] 2. Thread mechanical compression gauge into spark plug socket and hold throttle wide open.\n"
                "- [ ] 3. Crank engine 4-5 revolutions (Healthy: 140–180 PSI; Worn: < 110 PSI).\n"
                "- [ ] 4. Wet test: squirt 1 teaspoon of engine oil into spark hole; if PSI rises dramatically, piston rings are worn.\n"
                "- [ ] 5. If PSI remains unchanged, valve stem seals or guides are leaking oil down intake valves.\n\n"
                "[chips: Engine oil check | Spark plug check | Black smoke from exhaust]"
            )
        elif any(k in msg for k in ['black', 'dark smoke', 'soot', 'rich']):
            localized = _localized_branch('smoke_black', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Combustion analysis, {sir}. **Overly Rich Air-Fuel Mixture (Excess Fuel)**.\n\n"
                "**Interactive Carburetor & Fuel Checklist:**\n"
                "- [ ] 1. Inspect engine air filter — a clogged, oily air filter chokes airflow, causing severe rich mixture.\n"
                "- [ ] 2. Verify choke / enricher lever or plunger is retracting completely when warm.\n"
                "- [ ] 3. Remove spark plug: inspect for heavy dry black carbon deposits.\n"
                "- [ ] 4. For carburetor models: check float height and clean main/pilot jets with carb cleaner spray.\n"
                "- [ ] 5. For EFI models: verify oxygen (O2) sensor and engine coolant temperature (ECT) sensor wiring.\n\n"
                "[chips: Clean carburetor jets | Spark plug check | White sweet-smelling smoke]"
            )
        elif any(k in msg for k in ['white', 'steam', 'sweet']):
            localized = _localized_branch('smoke_white', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Thermal warning, {sir}. **Coolant Entering Combustion Chamber (Blown Head Gasket)**.\n\n"
                "**Cooling System Inspection Checklist:**\n"
                "- [ ] 1. Allow engine to cool completely before touching radiator cap.\n"
                "- [ ] 2. Check coolant level in recovery tank and radiator neck for milky residue or oil film.\n"
                "- [ ] 3. Inspect engine oil sight glass for milky white emulsion (water in oil).\n"
                "- [ ] 4. Perform a cooling system pressure test at 1.1 bar to verify head gasket seal integrity.\n\n"
                "[chips: Coolant & radiator check | Engine oil check | Blue smoke from exhaust]"
            )
        elif any(k in msg for k in ['sprocket', 'front sprocket', 'near engine', 'casing']):
            pass  # Fall through to database symptom match
        else:
            localized = _localized_branch('smoke_generic', lang, sir=sir, veh=veh_label)
            if localized:
                return localized
            return (
                f"Thermal and combustion analysis, {sir}. What colour or source of smoke are you observing?\n\n"
                "[chips: Blue smoke from exhaust | Black smoke from exhaust | White sweet-smelling smoke | Smoke near engine casing & sprocket]"
            )

    # 10. Greetings (checked after diagnostic branches so "hi"-prefixed
    # complaints like "hindi mag-start" or "high pitched squeal" are diagnosed
    # instead of being answered with a greeting)
    greetings = [
        'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy',
        'kamusta', 'kumusta', 'maayong adlaw', 'maayong aga', 'maayong hapon', 'maayong gab-i'
    ]
    if any(re.match(r'^' + re.escape(g) + r'\b', msg) for g in greetings):
        if lang == 'hiligaynon':
            return (
                f"Maayong adlaw, {sir}! Ako si J.A.R.V.I.S., imo personal diagnostic mechanic. "
                "Handa ako magbulig kay-o kag mag-diagnose sang imo motor ukon salakyan. "
                "Ano ang problema sang imo salakyan subong?\n\n"
                "[chips: Indi mag-andar ang makina | Humok ukon guba ang preno | Nagasiga ang temperature | Nagapiti-piti ang tambutso]"
            )
        elif lang == 'tagalog':
            return (
                f"Magandang araw, {sir}! Ako si J.A.R.V.I.S., ang iyong master mechanic assistant. "
                "Nakahanda akong mag-diagnose at magbigay ng gabay sa pagkukumpuni ng iyong motor o sasakyan. "
                "Anong problema ang nararanasan mo ngayon?\n\n"
                "[chips: Ayaw mag-start ng makina | Malambot ang preno | Umuusok ang tambutso | Kakaibang ingay sa makina]"
            )
        else:
            return (
                f"At your service, {sir}. J.A.R.V.I.S. online. Systems nominal. "
                "I am your master vehicle diagnostic mechanic. I can isolate vehicle faults, walk you through repair protocols, look up parts, and guide your repairs.\n\n"
                "What vehicle issue are you experiencing today?\n\n"
                "[chips: Engine won't start | Front brake not working | Engine overheating | Motorcycle won't accelerate properly]"
            )

    # 11. Identity
    if any(k in msg for k in ['who are you', 'what are you', 'your name', 'introduce yourself', 'sin-o ka', 'sino ka']):
        if lang == 'hiligaynon':
            return (
                f"Ako si J.A.R.V.I.S. (Just A Rather Very Intelligent System), {sir}. "
                "Ang imo mekaniko kag diagnostic assistant para sa motorsiklo kag mga salakyan.\n\n"
                "[chips: Bulig kag serbisyo | Indi mag-andar ang makina | Listahan sang mga pyesa]"
            )
        elif lang == 'tagalog':
            return (
                f"Ako si J.A.R.V.I.S. (Just A Rather Very Intelligent System), {sir}. "
                "Ang iyong digital master mechanic at diagnostic assistant para sa mga motor at sasakyan.\n\n"
                "[chips: Tulong at kakayahan | Ayaw mag-start ng makina | Listahan ng mga pyesa]"
            )
        else:
            return (
                f"I am J.A.R.V.I.S., Just A Rather Very Intelligent System. "
                f"I was built to keep this workshop operating at peak performance, {sir}: diagnose faults, "
                "pull repair protocols, inspect parts inventories, and offer a mechanic's second opinion before picking up a wrench.\n\n"
                "[chips: Help & capabilities | Engine won't start | List all parts]"
            )

    # 12. Help / Capabilities
    if any(k in msg for k in ['help', 'what can you do', 'capabilities', 'commands', 'bulig', 'tulong']):
        return (
            f"Of course, {sir}. My workshop diagnostic protocols include:\n\n"
            "• **Intelligent Triage** — Starting failure, braking faults, thermal overheating, transmission slip\n"
            "• **Interactive Protocols** — Checklists with specific tools and part specifications\n"
            "• **Parts Catalogue** — Specifications, part numbers, and estimated costs\n"
            "• **Safety Advisories** — Critical safety rules before road testing or servicing\n\n"
            "Select an issue or describe your vehicle symptoms:\n\n"
            "[chips: Engine won't start | Front brake not working | Engine overheating | Motorcycle won't accelerate properly]"
        )

    # 13. Database Diagnostic Symptoms & Troubleshooting Guides Matching
    # 14. Database Diagnostic Symptom Word Matching helper
    def _significant_word_hits(name, text):
        """Counts how significant (len>3) words of a DB name appear in the text."""
        significant = [w for w in name.split() if len(w) > 3]
        hits = sum(1 for w in significant if w in text)
        if name in text:
            return len(significant)
        # Require 2+ shared significant words (or the name's only significant
        # word) so queries like "clean my front wheel" don't match the
        # "Smoke near engine and front sprocket" symptom.
        if len(significant) <= 1:
            return hits
        return hits if hits >= 2 else 0

    symptoms = DiagnosticSymptom.objects.all()
    matched_symptom = None
    for symptom in symptoms:
        if _significant_word_hits(symptom.symptom_name.lower(), msg) > 0:
            matched_symptom = symptom
            break

    if matched_symptom:
        guides = TroubleshootingGuide.objects.filter(
            symptom=matched_symptom
        ).prefetch_related('required_parts__part')[:5]

        response_lines = [
            f"Diagnostic scan complete, {sir}. Match confirmed in workshop records: **{matched_symptom.symptom_name}** "
            f"(Category: {matched_symptom.category}).\n"
        ]

        if matched_symptom.description:
            response_lines.append(f"**Briefing:** {matched_symptom.description}\n")

        if guides:
            response_lines.append("**Interactive Repair Protocol:**\n")
            for i, guide in enumerate(guides, 1):
                response_lines.append(f"**Likely Cause:** {guide.possible_cause}")
                if guide.advice_notes:
                    response_lines.append(f"**Caution:** {guide.advice_notes}\n")

                steps = [
                    re.sub(r'^\s*(?:step\s*)?\d+[\.\):\-]\s*', '', line.strip(), flags=re.IGNORECASE)
                    for line in guide.repair_instructions.splitlines()
                    if line.strip()
                ]
                if not steps and guide.repair_instructions.strip():
                    steps = [guide.repair_instructions.strip()]

                for step_idx, step_text in enumerate(steps, 1):
                    response_lines.append(f"- [ ] {step_idx}. {step_text}")

                required_parts = guide.required_parts.all()
                if required_parts:
                    parts_str = ', '.join(
                        f"{rp.part.part_name} (×{rp.quantity_needed})"
                        for rp in required_parts
                    )
                    response_lines.append(f"\n**Required parts:** {parts_str}")
                response_lines.append("")

            response_lines.append(
                "[chips: What tools do I need for this? | Show required parts cost | Check engine oil]"
            )
        else:
            response_lines.append(
                "I have the symptom on file, but no repair protocol is linked yet. "
                "A qualified mechanic inspection is advised."
            )

        return '\n'.join(response_lines)

    # 15. Database Parts Lookup
    parts = Part.objects.all()
    for part in parts:
        if _significant_word_hits(part.part_name.lower(), msg) > 0:
            guides = TroubleshootingGuide.objects.filter(
                required_parts__part=part
            ).select_related('symptom').distinct()[:5]

            lines = [
                f"Located in workshop inventory, {sir}: **{part.part_name}**\n",
                f"• Part number: {part.part_number or 'N/A'}",
                f"• Category: {part.category or 'General'}",
                f"• Estimated cost: ${part.estimated_cost}\n",
            ]

            if guides:
                lines.append("**Used in repair protocols for:**")
                for g in guides:
                    lines.append(f"• {g.symptom.symptom_name} — {g.possible_cause}")

            lines.append("\n[chips: List all parts | Ask diagnostic question | Starting failure scan]")
            return '\n'.join(lines)

    # 16. Stats Queries
    if any(k in msg for k in ['how many symptoms', 'total symptoms', 'count symptoms']):
        count = DiagnosticSymptom.objects.count()
        localized = _localized_branch('stats_symptoms', lang, sir=sir, count=count)
        if localized:
            return localized
        return (
            f"Diagnostic archive reports **{count}** known vehicle symptoms on file, {sir}.\n\n"
            "[chips: List all symptoms | How many guides | How many parts]"
        )

    if any(k in msg for k in ['how many parts', 'total parts', 'count parts']):
        count = Part.objects.count()
        localized = _localized_branch('stats_parts', lang, sir=sir, count=count)
        if localized:
            return localized
        return (
            f"Parts catalogue reports **{count}** catalogued components, {sir}.\n\n"
            "[chips: List all parts | Ask diagnostic question | Starting failure scan]"
        )

    if any(k in msg for k in ['how many guides', 'total guides', 'troubleshooting count']):
        count = TroubleshootingGuide.objects.count()
        localized = _localized_branch('stats_guides', lang, sir=sir, count=count)
        if localized:
            return localized
        return (
            f"I have **{count}** troubleshooting protocols ready in the workshop archive, {sir}.\n\n"
            "[chips: List all symptoms | List all parts | Engine won't start]"
        )

    if any(k in msg for k in ['list symptoms', 'show symptoms', 'all symptoms', 'symptoms list']):
        symptoms_list = DiagnosticSymptom.objects.values_list('symptom_name', flat=True)[:20]
        if symptoms_list:
            chips = ' | '.join(symptoms_list[:4])
            s_str = '\n'.join(f"• {s}" for s in symptoms_list)
            return (
                f"Pulling the diagnostic symptom index now, {sir}:\n\n{s_str}\n\n"
                f"[chips: {chips}]"
            )
        return f"The diagnostic archive is currently empty, {sir}."

    if any(k in msg for k in ['list parts', 'show parts', 'all parts', 'parts list']):
        available_parts = Part.objects.values('part_name', 'category', 'estimated_cost')[:20]
        if available_parts:
            p_str = '\n'.join(
                f"• {p['part_name']} ({p['category'] or 'General'}) — ${p['estimated_cost']}"
                for p in available_parts
            )
            return (
                f"Here is the workshop parts inventory, {sir}:\n\n{p_str}\n\n"
                "[chips: Engine won't start | Front brake not working | Strange engine noise]"
            )
        return f"No parts are catalogued yet, {sir}."

    # 17. General Maintenance Protocols
    general_responses = {
        ('tool', 'tools', 'equipment needed'): (
            f"Standard workshop tool checklist, {sir}:\n\n"
            "- [ ] 1. Metric socket set (8mm, 10mm, 12mm, 14mm, 17mm, 19mm)\n"
            "- [ ] 2. Combination open-end wrenches\n"
            "- [ ] 3. JIS / Phillips and flathead screwdrivers\n"
            "- [ ] 4. Digital Multimeter (for electrical, battery, and sensor testing)\n"
            "- [ ] 5. Spark plug socket wrench with rubber insert\n"
            "- [ ] 6. Clean oil catch pan and lint-free shop towels\n"
            "- [ ] 7. Nitrile work gloves & eye protection\n\n"
            "[chips: Starting failure scan | Front brake not working | Acoustic noise scan]"
        ),
        ('oil', 'engine oil', 'oil change', 'langis'): (
            f"Engine lubrication protocol, {sir}:\n\n"
            "- [ ] 1. Warm engine 3 minutes, then shut off and keep vehicle upright on level ground.\n"
            "- [ ] 2. Inspect sight glass or clean dipstick: oil should sit between MIN and MAX marks.\n"
            "- [ ] 3. Place drain pan below crankcase; remove drain bolt (replace crush washer upon reassembly).\n"
            "- [ ] 4. Replace spin-on or cartridge oil filter and torque to manufacturer specification.\n"
            "- [ ] 5. Refill with recommended JASO-MA2 motorcycle 4T oil (do not use passenger car oil with friction modifiers).\n\n"
            "[chips: Smoke near engine casing & sprocket | How many parts | Starting failure scan]"
        ),
        ('battery', 'car battery', 'dead battery', 'battery diagnostic', 'baterya'): (
            f"Power-cell diagnostics, {sir}:\n\n"
            "• Healthy battery reads **12.6V+** at rest\n"
            "• At **12.0V or below**, battery is 75% discharged\n"
            "• Cranking voltage must not fall below **9.6V**\n"
            "• Typical motorcycle AGM/Lithium battery lifespan: 3–5 years\n\n"
            "[chips: Rapid clicking sound | Cranks slowly but won't start | Where is the main fuse?]"
        ),
        ('tyre', 'tire', 'flat tyre', 'flat tire', 'goma'): (
            f"Tyre safety protocol, {sir}:\n\n"
            "- [ ] 1. Check cold tyre pressure weekly (typically 29–33 PSI front, 33–36 PSI rear).\n"
            "- [ ] 2. Inspect tread depth indicators — replace if tread is under 1.6 mm.\n"
            "- [ ] 3. Check for cracks, dry rot on sidewalls, or embedded nails/screws.\n"
            "- [ ] 4. Inspect wheel valve stem rubber for weathering or leakage.\n\n"
            "[chips: Front brake not working | Starting failure scan | Help & capabilities]"
        ),
        ('spark plug', 'ignition', 'misfire'): (
            f"Ignition protocol, {sir}:\n\n"
            "- [ ] 1. Remove spark plug using dedicated rubber-lined plug socket.\n"
            "- [ ] 2. Inspect electrode color: light tan/grey is optimal; black soot indicates rich mixture; blistered white indicates lean.\n"
            "- [ ] 3. Measure electrode gap using wire feeler gauge (typically 0.7–0.8 mm).\n"
            "- [ ] 4. Clean electrode with brass wire brush or replace with fresh spark plug.\n\n"
            "[chips: Cranks normally, no combustion | Black smoke from exhaust | Starting failure scan]"
        ),
    }

    general_keys = ['proto_tools', 'proto_oil', 'proto_battery', 'proto_tyre', 'proto_sparkplug']
    for key, (keywords, response) in zip(general_keys, general_responses.items()):
        if any(k in msg for k in keywords):
            localized = _localized_branch(key, lang, sir=sir)
            if localized:
                return localized
            return response

    if any(k in msg for k in ['thank', 'thanks', 'bye', 'goodbye', 'salamat']):
        localized = _localized_branch('thanks', lang, sir=sir)
        if localized:
            return localized
        return (
            f"Always a pleasure, {sir}. J.A.R.V.I.S. will remain on standby. "
            "Drive safely, and do not hesitate to run another diagnostic scan whenever needed.\n\n"
            "[chips: Starting failure scan | Front brake not working | Acoustic noise scan]"
        )

    # 18. Friendly fallback — no vehicle form, just helpful guidance
    localized = _localized_branch('fallback', lang, sir=sir)
    if localized:
        return localized
    return (
        f"I'm not sure I caught that one, {sir}. "
        "Here is what I can help you with:\n\n"
        "• **Diagnostics** — Engine won't start, brake problems, overheating, acceleration issues\n"
        "• **Part explanations** — Ask me *\"What is a caliper?\"* or *\"What is a sprocket?\"* and I'll show you a photo\n"
        "• **Repair protocols** — Step-by-step interactive checklists for common fixes\n"
        "• **Parts inventory** — Costs, part numbers, and repair guides from the workshop database\n\n"
        "Try one of the options below, or describe your vehicle symptom in detail:\n\n"
        "[chips: Engine won't start | Front brake not working | What is a caliper? | What is a sprocket? | Oil change | Battery dead]"
    )


@login_required(login_url='login')
@require_POST
def jarvis_chat(request):
    try:
        data = json.loads(request.body or b'{}')
        if not isinstance(data, dict):
            raise ValueError
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid request'}, status=400)

    message = str(data.get('message') or '').strip()
    reset = bool(data.get('reset'))
    image_id = data.get('image_id')
    structured_mode = bool(data.get('structured')) or bool(image_id)

    # "Clear chat" closes the active server-side session and the guided
    # workflow state.  Legacy browser history is cleared by the client.
    if reset:
        request.session.pop('jarvis_guided', None)
        request.session.modified = True
        if structured_mode:
            conversation = get_or_create_conversation(
                request.user, data.get('conversation_id'), create=False,
            )
            if conversation is not None:
                assistant_service.reset(request.user, conversation.pk)
        if not message and not image_id:
            return JsonResponse({'ok': True, 'conversation_id': None})

    allowed, retry_after, _ = check_rate_limit(
        'chat', request.user.pk,
        limit=getattr(settings, 'CHAT_RATE_LIMIT_PER_MINUTE', 30),
        window_seconds=60,
    )
    if not allowed:
        return JsonResponse(
            {
                'error': 'Too many chat requests. Please wait a moment and try again.',
                'retry_after': retry_after,
            },
            status=429,
            headers={'Retry-After': str(retry_after)},
        )

    max_chars = (
        int(getattr(settings, 'ASSISTANT_MAX_MESSAGE_CHARS', 2000))
        if structured_mode else 1000
    )
    if len(message) > max_chars:
        return JsonResponse(
            {'error': f'Message too long (max {max_chars} characters)'},
            status=400,
        )
    if not message and not image_id:
        return JsonResponse({'error': 'Empty message'}, status=400)

    language = data.get('language')
    if language in ('auto', '', None):
        language = None
    experience_level = data.get('experience_level')
    if experience_level not in ('beginner', 'mechanic'):
        experience_level = 'beginner'

    quota = None
    if structured_mode:
        from apps.core.models import ImageUpload

        conversation = get_or_create_conversation(
            request.user, data.get('conversation_id'), create=True,
            language=language if language in ('english', 'tagalog', 'hiligaynon') else 'auto',
        )
        image = None
        if image_id:
            try:
                image_pk = int(image_id)
            except (TypeError, ValueError):
                return JsonResponse({'error': 'Invalid photo reference.'}, status=400)
            image = ImageUpload.objects.filter(pk=image_pk, user=request.user).first()
            if image is None:
                return JsonResponse({'error': 'Photo not found.'}, status=404)
            try:
                image = attach_to_conversation(image, conversation, request.user)
            except InvalidImageError as exc:
                return JsonResponse({'error': str(exc)}, status=400)

        request.session.pop('jarvis_guided', None)
        request.session.modified = True
        try:
            result = assistant_service.respond(
                request.user,
                message,
                conversation_id=conversation.pk,
                language=language,
                experience_level=experience_level,
                image=image,
            )
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        except Exception:
            logger.exception('Structured assistant failed')
            return JsonResponse(
                {'error': 'The diagnostic assistant could not complete that request. Please retry.'},
                status=500,
            )

        from apps.core.models import GeminiUsageTracker
        quota = GeminiUsageTracker.get_current_quota()
        result['quota'] = quota
        result['ai_available'] = is_ai_available()
        result['ai_configured'] = is_ai_configured()
        if image is not None:
            result['image_id'] = image.pk
            result['image_url'] = reverse('jarvis_image', args=[image.pk])
        return JsonResponse(result)

    # Guided narrowing state (identify motorcycle -> narrow the fault).
    # Kept in the Django session so it survives turns and page navigation.
    guided_state = request.session.get('jarvis_guided')
    if not isinstance(guided_state, dict):
        guided_state = {}

    reply = _jarvis_response(
        message, request.user, history=data.get('history', []), language=language,
        experience_level=experience_level, guided_state=guided_state,
    )

    if guided_state:
        request.session['jarvis_guided'] = guided_state
    else:
        request.session.pop('jarvis_guided', None)
    request.session.modified = True

    from apps.core.models import GeminiUsageTracker
    quota = GeminiUsageTracker.get_current_quota()

    return JsonResponse({
        'reply': reply,
        'quota': quota,
    })


@login_required(login_url='login')
@require_POST
def jarvis_image_upload(request):
    allowed, retry_after, _ = check_rate_limit(
        'upload', request.user.pk,
        limit=getattr(settings, 'UPLOAD_RATE_LIMIT_PER_MINUTE', 10),
        window_seconds=60,
    )
    if not allowed:
        return JsonResponse(
            {
                'error': 'Too many photo uploads. Please wait a moment and try again.',
                'retry_after': retry_after,
            },
            status=429,
            headers={'Retry-After': str(retry_after)},
        )

    upload = request.FILES.get('image') or request.FILES.get('photo')
    if upload is None:
        return JsonResponse({'error': 'Choose a photo to upload.'}, status=400)

    conversation = None
    conversation_id = request.POST.get('conversation_id')
    if conversation_id:
        conversation = get_or_create_conversation(
            request.user, conversation_id, create=False,
        )
        if conversation is None:
            return JsonResponse({'error': 'Conversation not found.'}, status=404)

    try:
        image = save_uploaded_image(
            request.user,
            upload,
            conversation=conversation,
            description=request.POST.get('description', ''),
        )
    except InvalidImageError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception:
        logger.exception('Chat photo upload failed')
        return JsonResponse(
            {'error': 'The photo could not be stored. Please retry with another image.'},
            status=500,
        )

    return JsonResponse({
        'ok': True,
        'image_id': image.pk,
        'url': reverse('jarvis_image', args=[image.pk]),
        'original_name': image.original_name,
        'mime_type': image.mime_type,
        'size': image.size,
        'width': image.width,
        'height': image.height,
        'conversation_id': image.conversation_id,
    })


@login_required(login_url='login')
@require_GET
def jarvis_image(request, image_id):
    from apps.core.models import ImageUpload

    image = ImageUpload.objects.filter(pk=image_id, user=request.user).first()
    if image is None:
        raise Http404('Photo not found.')
    try:
        handle = image.file.open('rb')
    except (OSError, ValueError) as exc:
        raise Http404('Photo file is unavailable.') from exc
    response = FileResponse(handle, content_type=image.mime_type or 'application/octet-stream')
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', image.original_name or 'photo.jpg')
    response['Content-Disposition'] = f'inline; filename="{safe_name}"'
    response['Cache-Control'] = 'private, max-age=300'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required(login_url='login')
@require_GET
def jarvis_status(request):
    """Return AI availability and the app's own usage budget.

    This deliberately does not expose the API key, provider quota, or raw
    provider errors.  The request budget is local to this application.
    """
    from apps.core.models import GeminiUsageTracker
    quota = GeminiUsageTracker.get_current_quota()
    return JsonResponse({
        'status': 'online',
        'quota': quota,
        'ai_configured': is_ai_configured(),
        'ai_available': is_ai_available(),
        'image_input_supported': bool(getattr(settings, 'GEMINI_INPUT_IMAGE_SUPPORTED', True)),
        'max_message_chars': int(getattr(settings, 'ASSISTANT_MAX_MESSAGE_CHARS', 2000)),
        'languages': ['english', 'tagalog', 'hiligaynon'],
    })
