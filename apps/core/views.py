import json
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
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

User = get_user_model()

# ---------------------------------------------------------------------------
# Gemini AI client setup (using google-genai SDK)
# ---------------------------------------------------------------------------
_gemini_client = None


def _get_gemini_client():
    """Lazily initialise and return the Gemini AI client."""
    global _gemini_client
    if _gemini_client is None and getattr(settings, 'GEMINI_API_KEY', ''):
        from google import genai
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
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


@login_required(login_url='login')
def home(request):
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
    return redirect('dashboard')


# ---------------------------------------------------------------------------
# Jarvis AI Chat
# ---------------------------------------------------------------------------

def _jarvis_address(user):
    first = (getattr(user, 'first_name', '') or '').strip()
    return first if first else 'sir'


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
        'umuusok', 'usok', 'paano', 'salamat', 'kasi', 'sasakyan', 'kotse', 'kumatok'
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
    corpus = (text or '').lower()
    if history and isinstance(history, list):
        for turn in history:
            corpus += " " + (turn.get('text', '') or '').lower()

    info = {
        'make': None,
        'model': None,
        'year': None,
        'type': None,
        'brake_type': None,
        'engine_fuel': None,
        'displacement': None,
    }

    # 1. Direct parsing for structured form submissions (e.g. "Vehicle: 2022 Honda Click 125i (Scooter, 125cc, Fuel-injected)")
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
    if not info['make']:
        for m in makes:
            if re.search(r'\b' + re.escape(m) + r'\b', corpus):
                info['make'] = m.title()
                break

    models_list = [
        'click 125i', 'click 150i', 'click 160', 'click',
        'aerox 155', 'aerox', 'nmax 155', 'nmax',
        'raider 150', 'raider', 'mio sporty', 'mio i 125', 'mio gear', 'mio soul', 'mio',
        'fazzio', 'gravis', 'burgman street', 'burgman',
        'beat', 'pcx 160', 'pcx 150', 'pcx', 'adv 160', 'adv 150', 'adv',
        'sniper 155', 'sniper 150', 'sniper',
        'tmx 125', 'tmx supremo', 'tmx', 'barako 175', 'barako', 'ct100', 'ct125',
        'wave 110', 'wave 125', 'wave', 'xrm 125', 'xrm', 'smash 115', 'smash',
        'vios', 'mirage g4', 'mirage', 'wigo', 'innova', 'fortuner', 'hilux',
        'civic', 'corolla', 'city', 'almera', 'rush', 'raize', 'montero'
    ]
    if not info['model']:
        for mdl in models_list:
            if mdl in corpus:
                info['model'] = mdl.title()
                break

    if not info['year']:
        year_match = re.search(r'\b(19[89]\d|20[012]\d)\b', corpus)
        if year_match:
            info['year'] = year_match.group(1)

    if any(k in corpus for k in ['scooter', 'click', 'aerox', 'nmax', 'mio', 'beat', 'pcx', 'adv', 'fazzio', 'burgman']):
        info['type'] = 'scooter'
    elif any(k in corpus for k in ['car', 'sedan', 'suv', 'van', 'truck', 'kotse', 'awto', 'salakyan', 'vios', 'wigo']):
        info['type'] = 'car'
    elif any(k in corpus for k in ['tricycle', 'toda', 'trike']):
        info['type'] = 'tricycle'
    elif any(k in corpus for k in ['motorcycle', 'motor', 'bike', 'underbone']):
        info['type'] = 'motorcycle'

    if 'disc' in corpus or 'disk' in corpus or 'caliper' in corpus:
        info['brake_type'] = 'disc'
    elif 'drum' in corpus or 'tambor' in corpus:
        info['brake_type'] = 'drum'

    if any(k in corpus for k in ['fi', 'pgm-fi', 'fuel inject', 'injected', 'injection']):
        info['engine_fuel'] = 'FI'
    elif any(k in corpus for k in ['carb', 'carburetor', 'karburador']):
        info['engine_fuel'] = 'Carburetor'

    disp_match = re.search(r'\b(\d{2,4}\s?cc|\d\.\d\s?[lL])\b', corpus)
    if disp_match:
        info['displacement'] = disp_match.group(1).upper()

    return info


def _jarvis_gemini(message, user, history=None):
    """
    Calls Gemini AI with full multi-turn conversational vehicle diagnostic mechanic system.
    """
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
        for turn in history[-8:]:
            r = "User" if turn.get('role') == 'user' else "J.A.R.V.I.S."
            txt = turn.get('text', '').strip()
            txt = re.sub(r'\[chips:.*?\]', '', txt).strip()
            if txt:
                formatted_turns.append(f"{r}: {txt}")
        if formatted_turns:
            convo_history_str = (
                "\n## PREVIOUS CONVERSATION TURNS (Analyze what vehicle details & symptoms the user has ALREADY provided — DO NOT re-ask answered questions):\n"
                + "\n".join(formatted_turns)
                + "\n"
            )

    full_prompt = f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the master vehicle diagnostic mechanic and repair assistant for an automotive and motorcycle workshop. You diagnose motorcycles, scooters, underbones, tricycles, cars, SUVs, and light trucks. You speak like Tony Stark's assistant: professional, courteous, precise, witty, and prioritizing safety above all else. Address the user respectfully as '{sir}'.

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

## 5. MULTILINGUAL SUPPORT (TAGALOG & HILIGAYNON)
- Fluently understand and respond in English, Tagalog / Filipino / Taglish, and Hiligaynon (Ilonggo).
- ALWAYS respond in the SAME language or dialect used by the user:
  * If the user speaks in Hiligaynon (e.g., "Maayong adlaw", "preno ko guba", "indi mag-andar", "nagasiga ang temperature", "nagapiti-piti ang tambutso"), answer fluently and naturally in Hiligaynon with polite mechanic tone ("sir" / "bossing"), using natural local terms (preno, disc brake, drum brake, tambutso, makina, spark plug, langis, kadena, baterya).
  * If the user speaks in Tagalog / Taglish (e.g., "Kamusta", "ayaw mag-start ng motor ko", "malambot ang preno", "umuusok"), reply in natural Tagalog/Taglish.
  * If the user speaks in English, reply in English.

## 6. INTERACTIVE ACTION CHIPS
- Conclude EVERY response with 3 to 5 clickable action chips matching the most relevant choices or answers in this exact format:
  `[chips: Option 1 | Option 2 | Option 3 | Option 4]`

{convo_history_str}
## CURRENT USER MESSAGE
User: {message}

Your response as J.A.R.V.I.S.:"""

    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=full_prompt,
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
    except Exception:
        return None


def _normalize_tokens(text):
    """Extracts meaningful normalized lowercase words, excluding common stop words."""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    stop_words = {
        'what', 'is', 'the', 'a', 'an', 'how', 'do', 'does', 'can', 'my', 'to',
        'of', 'for', 'in', 'on', 'at', 'by', 'and', 'or', 'with', 'from', 'about',
        'why', 'when', 'where', 'who', 'tell', 'me', 'please', 'help', 'jarvis',
        'sir', 'there', 'this', 'that', 'are', 'was', 'were', 'will', 'would', 'should'
    }
    tokens = [w for w in clean.split() if len(w) >= 3 and w not in stop_words]
    return tokens


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

        # 2. Overlap search on keywords
        candidates = JarvisKnowledge.objects.all()[:150]
        best_match = None
        best_score = 0.0

        for item in candidates:
            item_tokens = set(item.keywords.split())
            if not item_tokens:
                continue
            common = query_tokens.intersection(item_tokens)
            if not common:
                continue
            score = len(common) / len(query_tokens)
            if score > best_score:
                best_score = score
                best_match = item

        # Require at least 50% match or 2+ shared keywords
        if best_match:
            overlap_count = len(query_tokens.intersection(set(best_match.keywords.split())))
            if best_score >= 0.5 or overlap_count >= 2:
                best_match.hit_count += 1
                best_match.save(update_fields=['hit_count', 'updated_at'])
                return best_match.ai_response

    except Exception:
        pass

    return None


def _jarvis_response(message, user, history=None):
    """
    Primary: tries Gemini AI with full motor context & multi-turn history.
    Fallback 1: Offline Knowledge Cache (answers previously saved from Gemini).
    Fallback 2: Upgraded Rule-based interactive J.A.R.V.I.S. diagnostic engine.
    """
    # 1. Try Gemini first (Online)
    gemini_reply = _jarvis_gemini(message, user, history=history)
    if gemini_reply:
        return gemini_reply

    # 2. Fallback: Search Offline Knowledge Cache (Offline)
    cached_reply = _find_offline_knowledge(message, user)
    if cached_reply:
        return cached_reply

    # 3. Fallback: Upgraded rule-based interactive mechanic engine
    return _jarvis_rule_based_diagnostic(message, user, history=history)


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

    # 1. Greetings
    greetings = [
        'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy',
        'kamusta', 'kumusta', 'maayong adlaw', 'maayong aga', 'maayong hapon', 'maayong gab-i'
    ]
    if any(msg.startswith(g) for g in greetings):
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

    # 2. Identity
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

    # 3. Help / Capabilities
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

    # 4. Brake Diagnostic System (Intake -> Specific Questions -> Protocol)
    brake_triggers = ['brake', 'brakes', 'preno', 'stopping', 'lever soft', 'pedal soft', 'preho']
    if any(k in msg for k in brake_triggers) and not any(k in msg for k in ['list parts', 'parts list']):
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
        return (
            f"Diagnostic protocol engaged for your **{veh_label}**, {sir}.\n\n"
            "To isolate the fault immediately, **what occurs when you press the starter?**\n\n"
            '[vehicle-form: {"category": "start"}]\n'
            "[chips: Rapid clicking sound | Cranks normally, no combustion | Cranks slowly but won't start | Completely dead - no lights]"
        )

    # Sub-branches for Starting Symptoms (clickable chips or direct text)
    if any(k in msg for k in ['rapid clicking', 'clicking sound', 'starter clicking', 'relay clicking', 'clicks but', 'clicking noise', 'lagatik']):
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
            return (
                f"Acoustic scanner active, {sir}. Where is the mechanical noise localized?\n\n"
                "[chips: Metallic ticking from top end | Deep knocking from bottom end | Rattling / slapping from side casing | High-pitched squeal on acceleration]"
            )

    # 9. Smoke / Thermal Diagnostic Tree
    if any(k in msg for k in ['smoke', 'smoking', 'exhaust smoke', 'fumes', 'usok', 'aso']):
        if any(k in msg for k in ['blue', 'bluish', 'oil smoke']):
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
            return (
                f"Thermal and combustion analysis, {sir}. What colour or source of smoke are you observing?\n\n"
                "[chips: Blue smoke from exhaust | Black smoke from exhaust | White sweet-smelling smoke | Smoke near engine casing & sprocket]"
            )

    # 10. Database Diagnostic Symptoms & Troubleshooting Guides Matching
    symptoms = DiagnosticSymptom.objects.all()
    matched_symptom = None
    for symptom in symptoms:
        if symptom.symptom_name.lower() in msg or any(
            word in msg for word in symptom.symptom_name.lower().split()
            if len(word) > 3
        ):
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

    # 11. Database Parts Lookup
    parts = Part.objects.all()
    for part in parts:
        if part.part_name.lower() in msg or any(
            word in msg for word in part.part_name.lower().split()
            if len(word) > 3
        ):
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

    # 12. Stats Queries
    if any(k in msg for k in ['how many symptoms', 'total symptoms', 'count symptoms']):
        count = DiagnosticSymptom.objects.count()
        return (
            f"Diagnostic archive reports **{count}** known vehicle symptoms on file, {sir}.\n\n"
            "[chips: List all symptoms | How many guides | How many parts]"
        )

    if any(k in msg for k in ['how many parts', 'total parts', 'count parts']):
        count = Part.objects.count()
        return (
            f"Parts catalogue reports **{count}** catalogued components, {sir}.\n\n"
            "[chips: List all parts | Ask diagnostic question | Starting failure scan]"
        )

    if any(k in msg for k in ['how many guides', 'total guides', 'troubleshooting count']):
        count = TroubleshootingGuide.objects.count()
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
        parts_list = Part.objects.values('part_name', 'category', 'estimated_cost')[:20]
        if parts_list:
            p_str = '\n'.join(
                f"• {p['part_name']} ({p['category'] or 'General'}) — ${p['estimated_cost']}"
                for p in parts_list
            )
            return (
                f"Here is the workshop parts inventory, {sir}:\n\n{p_str}\n\n"
                "[chips: Engine won't start | Front brake not working | Strange engine noise]"
            )
        return f"No parts are catalogued yet, {sir}."

    # 13. General Maintenance Protocols
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

    for keywords, response in general_responses.items():
        if any(k in msg for k in keywords):
            return response

    if any(k in msg for k in ['thank', 'thanks', 'bye', 'goodbye', 'salamat']):
        return (
            f"Always a pleasure, {sir}. J.A.R.V.I.S. will remain on standby. "
            "Drive safely, and do not hesitate to run another diagnostic scan whenever needed.\n\n"
            "[chips: Starting failure scan | Front brake not working | Acoustic noise scan]"
        )

    # 14. Fallback with helpful interactive chips
    return (
        f"I am ready to diagnose your vehicle, {sir}. "
        "Select a diagnostic category below, or describe the specific symptom:\n\n"
        "[chips: Engine won't start | Front brake not working | Engine overheating | Motorcycle won't accelerate properly | "
        "Strange engine noise | Smoke from exhaust | Battery dead | Oil change]"
    )


@login_required(login_url='login')
@require_http_methods(['POST'])
def jarvis_chat(request):
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        history = data.get('history', [])
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid request'}, status=400)

    if not message:
        return JsonResponse({'error': 'Empty message'}, status=400)

    if len(message) > 1000:
        return JsonResponse({'error': 'Message too long (max 1000 chars)'}, status=400)

    reply = _jarvis_response(message, request.user, history=history)

    from apps.core.models import GeminiUsageTracker
    quota = GeminiUsageTracker.get_current_quota()

    return JsonResponse({
        'reply': reply,
        'quota': quota,
    })


@login_required(login_url='login')
@require_http_methods(['GET'])
def jarvis_status(request):
    """Returns current Gemini API quota and usage statistics."""
    from apps.core.models import GeminiUsageTracker
    quota = GeminiUsageTracker.get_current_quota()
    return JsonResponse({
        'status': 'online',
        'quota': quota,
    })
