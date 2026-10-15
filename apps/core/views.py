import json
import re
from datetime import timedelta

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


def _jarvis_response(message, user):
    """
    Rule-based interactive J.A.R.V.I.S. diagnostic engine.
    Speaks like Tony Stark's assistant with interactive diagnostic trees,
    step-by-step checklists, and follow-up choice chips.
    """
    from apps.motor.models import DiagnosticSymptom, Part, TroubleshootingGuide

    msg = message.lower().strip()
    sir = _jarvis_address(user)

    # 1. Greetings
    greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy']
    if any(msg.startswith(g) for g in greetings):
        return (
            f"At your service, {sir}. J.A.R.V.I.S. online. Systems nominal. "
            "I can run live diagnostics, walk you through repair protocols, look up parts, "
            "and guide you through motorcycle repairs.\n\n"
            "Select an issue below or tell me what is happening with your motorcycle:\n\n"
            "[chips: Engine won't start | Spongy brakes | Strange engine noise | Smoke from exhaust]"
        )

    # 2. Identity
    if any(k in msg for k in ['who are you', 'what are you', 'your name', 'introduce yourself']):
        return (
            f"I am J.A.R.V.I.S., Just A Rather Very Intelligent System. "
            f"I was built to keep this workshop running, {sir}: diagnose faults, "
            "pull repair guides, catalogue parts, and offer a second opinion before you pick up a wrench.\n\n"
            "[chips: Help & capabilities | Engine won't start | List all parts]"
        )

    # 3. Help / Capabilities (student budget focus)
    if any(k in msg for k in ['help', 'what can you do', 'capabilities', 'commands']):
        return (
            f"Of course, {sir}. My current interactive protocols include:\n\n"
            "• **Diagnostic Triage** — Starting failure, acoustic analysis, braking, thermal issues\n"
            "• **Step-by-Step Protocols** — Interactive checklists you can check off as you work\n"
            "• **Parts Catalogue** — Specifications, part numbers, and estimated costs\n"
            "• **Archive Stats** — Known symptoms and troubleshooting guides\n\n"
            "💡 **College student special:** Most protocols include budget-friendly alternatives — "
            "reuse parts, borrow tools from the campus workshop, or try temporary fixes to get you to class.\n\n"
            "Choose a diagnostic scanner or describe your motorcycle problem:\n\n"
            "[chips: Starting failure scan | Brake system check | Acoustic noise scan | List all parts]"
        )

    # 4. Starting Failure Diagnostic Tree (Feature 2 & 3)
    starting_triggers = [
        "won't start", "wont start", "cant start", "cannot start", "doesn't start",
        "doesnt start", "not starting", "hard to start", "starting problem", "trouble starting",
        "starting issue", "no start", "fail to start", "fails to start", "starting failure scan"
    ]
    if any(k in msg for k in starting_triggers):
        return (
            f"Diagnostic protocol engaged, {sir}. Starting failures typically isolate into "
            "electrical (battery/relay), ignition (spark), or fuel delivery systems.\n\n"
            "To pinpoint the exact root cause immediately, **what occurs when you press the starter button?**\n\n"
            "[chips: Rapid clicking sound | Cranks slowly but won't start | Cranks normally, no combustion | Completely dead - no lights]"
        )

    # Branch 4a: Rapid clicking sound
    if any(k in msg for k in ['rapid clicking', 'clicking sound', 'starter clicking', 'relay clicking', 'clicks but', 'clicking noise']):
        return (
            f"Analysis complete, {sir}. **Starter Solenoid Relay Chatter** detected.\n\n"
            "**Root Cause:** The battery has enough nominal voltage (12V) to engage the relay coil, "
            "but under the heavy 50-80 Amp load of the starter motor, terminal voltage collapses below 10.5V. "
            "The relay disengages, voltage rebounds, engages again, causing high-frequency clicking.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Switch off ignition and inspect 10mm battery terminal bolts for looseness or white sulfate corrosion.\n"
            "- [ ] 2. Measure resting voltage with a multimeter (Healthy: 12.6V+; Discharged: < 12.0V).\n"
            "- [ ] 3. Measure battery voltage while holding the starter button (If below 9.6V, battery cells are degraded).\n"
            "- [ ] 4. Connect a 12V motorcycle smart trickle charger or test with a known good 12V battery.\n"
            "- [ ] 5. Check main heavy ground cable bolted to the engine casing for rust or loose connection.\n\n"
            "[chips: How to test battery with multimeter | Test starter relay | Cranks slowly but won't start]"
        )

    # Branch 4b: Cranks slowly
    if any(k in msg for k in ['cranks slowly', 'slow crank', 'cranking slow', 'turning slow', 'sluggish crank']):
        return (
            f"Analysis complete, {sir}. **High Mechanical Drag or Low Cranking Amperage**.\n\n"
            "**Root Cause:** The starter motor is receiving insufficient current or fighting excessive mechanical resistance.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Check engine oil level and viscosity — overly heavy or cold oil creates severe drag.\n"
            "- [ ] 2. Inspect negative battery ground lead bolted to the engine case for paint, rust, or loose bolt.\n"
            "- [ ] 3. Perform a voltage drop test across starter relay terminals during cranking (should be < 0.5V).\n"
            "- [ ] 4. Inspect starter motor carbon brushes for wear or oil ingress through the starter shaft seal.\n\n"
            "[chips: Rapid clicking sound | Battery diagnostic | Engine oil check]"
        )

    # Branch 4c: Cranks normally but won't fire (no combustion)
    if any(k in msg for k in [
        'cranks normally', 'no combustion', 'cranks but', 'wont fire', "won't fire",
        'cranking fine', 'engine spins but', 'no spark'
    ]):
        return (
            f"Combustion triangle analysis, {sir}. The starter spins smoothly, ruling out the starter motor and battery.\n\n"
            "The engine is missing either **Spark**, **Fuel**, or **Compression**.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Verify handlebar engine kill switch is set to 'RUN' and side-stand is fully retracted.\n"
            "- [ ] 2. Remove spark plug; rest grounded metal threads against cylinder head and crank to inspect for crisp blue spark.\n"
            "- [ ] 3. Inspect spark plug tip: if wet and smelling of gas, engine is flooded; if bone dry, fuel is not reaching cylinder.\n"
            "- [ ] 4. Verify fuel petcock/valve is open and fuel tank vent line is not clogged or pinched.\n"
            "- [ ] 5. For carburetor models: drain float bowl to check for water/sediment; for EFI: listen for fuel pump priming whine.\n\n"
            "[chips: How to test spark plug | Engine flooded protocol | Clean carburetor jets]"
        )

    # Branch 4d: Completely dead / no lights
    if any(k in msg for k in ['completely dead', 'no lights', 'no power', 'no dash', 'nothing happens', 'no electric']):
        return (
            f"Analysis complete, {sir}. **Total Electrical Circuit Interruption**.\n\n"
            "**Root Cause:** Power is prevented from reaching the ignition switch and main bus.\n\n"
            "**Interactive Troubleshooting Checklist:**\n"
            "- [ ] 1. Check the Main 30A Fuse (typically housed directly inside or beside the starter solenoid).\n"
            "- [ ] 2. Check battery terminal connections — clean oxidation and ensure 10mm bolts are snug.\n"
            "- [ ] 3. Check key ignition switch wiring harness connector under the fuel tank / triple tree.\n"
            "- [ ] 4. Test battery terminal voltage with a multimeter — verify it is not reversed or completely dead (0V).\n\n"
            "[chips: Where is the main fuse? | Rapid clicking sound | Check battery voltage]"
        )

    # 5. Brake System Diagnostic Tree (Feature 2 & 3)
    if any(k in msg for k in ['brake system check', 'brake', 'brakes', 'stopping issue', 'lever soft']) and not any(k in msg for k in ['list parts', 'parts list']):
        if any(k in msg for k in ['spongy', 'soft', 'mushy', 'lever pulls to bar', 'fade']):
            return (
                f"Brake safety briefing, {sir}. **Air Ingress or Fluid Contamination** in hydraulic line.\n\n"
                "**Root Cause:** Air bubbles are compressible, causing hydraulic pressure loss when you pull the lever.\n\n"
                "**Brake Bleeding & Restoration Checklist:**\n"
                "- [ ] 1. Level handlebars and clean master cylinder reservoir cap before opening.\n"
                "- [ ] 2. Remove cap, verify diaphragm condition, and top up with fresh DOT 4 brake fluid.\n"
                "- [ ] 3. Attach 8mm wrench and clear vinyl tubing to caliper bleeder valve into a catch bottle.\n"
                "- [ ] 4. Squeeze brake lever firmly 3 times and hold it pressed against the grip.\n"
                "- [ ] 5. Crack open bleeder valve for 1 second until fluid squirts, then close before releasing lever.\n"
                "- [ ] 6. Repeat until zero air bubbles appear in tubing and lever resistance becomes solid.\n\n"
                "[chips: What brake fluid type? | How to inspect brake pads | Check brake disc]"
            )
        elif any(k in msg for k in ['squeak', 'squeal', 'chirp', 'high pitched']):
            return (
                f"Acoustic brake analysis, {sir}. **Glazed Brake Pads or Dust Contamination**.\n\n"
                "**Interactive Troubleshooting Checklist:**\n"
                "- [ ] 1. Inspect brake pad friction material thickness (replace if under 2.0 mm).\n"
                "- [ ] 2. Spray brake disc rotor and caliper with dedicated residue-free brake cleaner.\n"
                "- [ ] 3. Lightly scuff brake pad glaze using 240-grit sandpaper on a flat surface.\n"
                "- [ ] 4. Apply a minute dab of copper anti-seize paste to pad backing plate contact points (never on friction side).\n"
                "- [ ] 5. Retorque caliper mounting bolts to manufacturer specification.\n\n"
                "[chips: Spongy or soft brake lever | Metal grinding sound | List all parts]"
            )
        elif any(k in msg for k in ['grind', 'grinding', 'metal on metal']):
            return (
                f"CRITICAL WARNING, {sir}. **Severe Friction Material Depletion**.\n\n"
                "The brake pad friction compound is fully exhausted; the steel backing plate is directly gouging the rotor.\n\n"
                "**Emergency Replacement Checklist:**\n"
                "- [ ] 1. Park motorcycle immediately — prolonged metal-on-metal will destroy the rotor disc.\n"
                "- [ ] 2. Remove caliper retaining pins and slide out worn pad backings.\n"
                "- [ ] 3. Inspect rotor disc surface for deep grooves or blue thermal discoloration.\n"
                "- [ ] 4. Clean caliper piston seals with brake fluid and compress pistons back into bore.\n"
                "- [ ] 5. Install fresh sintered or ceramic brake pads and secure retaining pin cotter clips.\n\n"
                "[chips: List all parts | Spongy or soft brake lever | How many parts]"
            )
        else:
            return (
                f"Brake diagnostics online, {sir}. What specific symptom is the braking system exhibiting?\n\n"
                "[chips: Spongy or soft brake lever | Squeaking or high-pitched squeal | Metal grinding sound | Brake disc rotor pulsing]"
            )

    # 6. Engine Noise Diagnostic Tree (Feature 2 & 3)
    if any(k in msg for k in ['acoustic noise scan', 'noise', 'sound', 'knocking', 'ticking', 'rattling', 'slapping', 'clattering']):
        if any(k in msg for k in ['tick', 'ticking', 'tap', 'tapping', 'top end', 'valve']):
            return (
                f"Acoustic analysis, {sir}. **Excessive Valve Tappet Clearance** in cylinder head.\n\n"
                "**Interactive Valve Adjustment Checklist:**\n"
                "- [ ] 1. Allow engine to cool down completely (inspection must be performed at ambient room temp).\n"
                "- [ ] 2. Remove cylinder head valve inspection caps and alternator timing inspection plug.\n"
                "- [ ] 3. Rotate crankshaft with 14mm socket to Top Dead Center (TDC) on the compression stroke (T mark aligned).\n"
                "- [ ] 4. Insert feeler gauge between rocker arm adjuster screw and valve stem tip (e.g. 0.08mm intake / 0.12mm exhaust).\n"
                "- [ ] 5. Loosen 9mm locknut, adjust screw until slight resistance is felt on gauge, retighten locknut.\n\n"
                "[chips: Cam chain tensioner check | Oil pressure check | Strange engine noise]"
            )
        elif any(k in msg for k in ['knock', 'knocking', 'thud', 'bottom end', 'deep knock']):
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
                "- [ ] 2. Remove the center sealing bolt and spring to verify internal ratchet mechanism has not jammed.\n"
                "- [ ] 3. Manually turn tensioner screw clockwise to retract plunger, re-install, and release to reset tension.\n"
                "- [ ] 4. If noise persists, the cam chain guide slippers or chain links are stretched beyond service limits.\n\n"
                "[chips: Metallic ticking from top end | Oil pressure check | Strange engine noise]"
            )
        else:
            return (
                f"Acoustic scanner active, {sir}. Mechanical sounds provide pinpoint diagnostics. Where is the noise localized?\n\n"
                "[chips: Metallic ticking from top end | Deep knocking from bottom end | Rattling / slapping from side casing | High-pitched squeal on acceleration]"
            )

    # 7. Smoke / Thermal Diagnostic Tree (Feature 2 & 3)
    if any(k in msg for k in ['smoke', 'smoking', 'exhaust smoke', 'fumes']):
        if any(k in msg for k in ['blue', 'bluish', 'oil smoke']):
            return (
                f"Thermal analysis, {sir}. **Engine Oil Entering Combustion Chamber**.\n\n"
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
            # Fall through to match the database symptom!
            pass
        else:
            return (
                f"Thermal and combustion analysis, {sir}. What colour or source of smoke are you observing?\n\n"
                "[chips: Blue smoke from exhaust | Black smoke from exhaust | White sweet-smelling smoke | Smoke near engine casing & sprocket]"
            )

    # 8. Stats queries
    if any(k in msg for k in ['how many symptoms', 'total symptoms', 'count symptoms']):
        count = DiagnosticSymptom.objects.count()
        return (
            f"I've queried the diagnostic archive, {sir}. "
            f"There are currently **{count}** known symptoms on file.\n\n"
            f"💡 **Student money-saver:** Fixing issues yourself using these guides can save $150–$500 per repair vs. shop rates.\n"
            "[chips: List all symptoms | How many guides | How many parts]"
        )

    if any(k in msg for k in ['how many parts', 'total parts', 'count parts']):
        count = Part.objects.count()
        return (
            f"Parts catalogue reports **{count}** entries, {sir}.\n\n"
            f"💡 **Student tip:** Many parts can be sourced used or from salvage yards — typically 60–80% less than dealer prices.\n"
            "[chips: List all parts | Ask diagnostic question | Starting failure scan]"
        )

    if any(k in msg for k in ['how many guides', 'total guides', 'troubleshooting count']):
        count = TroubleshootingGuide.objects.count()
        return (
            f"I have **{count}** troubleshooting protocols ready, {sir}.\n\n"
            f"💡 **Student special:** These guides walk you through fixes step-by-step — often avoiding the $80–$150/min shop labor fee.\n"
            "[chips: List all symptoms | List all parts | Engine won't start]"
        )

    if any(k in msg for k in ['list symptoms', 'show symptoms', 'all symptoms', 'symptoms list']):
        symptoms = DiagnosticSymptom.objects.values_list('symptom_name', flat=True)[:20]
        if symptoms:
            chips = ' | '.join(symptoms[:4])
            symptom_list = '\n'.join(f"• {s}" for s in symptoms)
            return (
                f"Pulling the symptom index now, {sir}:\n\n{symptom_list}\n\n"
                f"[chips: {chips}]"
            )
        return f"The diagnostic archive is empty, {sir}. Nothing on file yet."

    if any(k in msg for k in ['list parts', 'show parts', 'all parts', 'parts list']):
        parts = Part.objects.values('part_name', 'category', 'estimated_cost')[:20]
        if parts:
            parts_list = '\n'.join(
                f"• {p['part_name']} ({p['category'] or 'General'}) — ${p['estimated_cost']}"
                for p in parts
            )
            return (
                f"Here is the parts inventory, {sir}:\n\n{parts_list}\n\n"
                "[chips: Engine won't start | Spongy brakes | Strange engine noise]"
            )
        return f"No parts are catalogued yet, {sir}."

    # 9. Database Symptoms & Guides Matching with Auto-Checklist formatting!
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
            f"Scan complete, {sir}. Match confirmed: **{matched_symptom.symptom_name}** "
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

                # Format repair instructions into an interactive checklist!
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
                "A qualified mechanic would be the prudent next call."
            )

        return '\n'.join(response_lines)

    # 10. Database Parts Lookup
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
                f"Located in inventory, {sir}: **{part.part_name}**\n",
                f"• Part number: {part.part_number or 'N/A'}",
                f"• Category: {part.category or 'General'}",
                f"• Estimated cost: ${part.estimated_cost}\n",
            ]

            if guides:
                lines.append("**Used in repairs for:**")
                for g in guides:
                    lines.append(f"• {g.symptom.symptom_name} — {g.possible_cause}")

            lines.append("\n[chips: List all parts | Ask diagnostic question | Starting failure scan]")
            # Budget-friendly tip for students
            cost = part.estimated_cost or 0
            if cost > 0:
                lines.append(f"\n💡 **Student tip:** Search for used/reconditioned parts on campus forums or salvage yards to save ~50%.")
            return '\n'.join(lines)

    # 11. Enhanced Tools Inquiry Handler
    if any(k in msg for k in ['tool', 'tools', 'equipment needed']):
        return (
            f"Standard workshop tool checklist, {sir}:\n\n"
            "- [ ] 1. Metric socket set (8mm, 10mm, 12mm, 14mm, 17mm, 19mm) — *Borrows from campus workshop or senior students*\n"
            "- [ ] 2. Combination open-end wrenches — *Often available from the department lab pool*\n"
            "- [ ] 3. JIS / Phillips and flathead screwdrivers — *Your basic set; try the student union first*\n"
            "- [ ] 4. Digital Multimeter (for electrical and battery testing) — *$10-$15 at discount stores; a worthwhile one-time investment*\n"
            "- [ ] 5. Spark plug socket wrench with rubber insert — *often fits multiple plug sizes*\n"
            "- [ ] 6. Clean oil catch pan and lint-free shop towels — *any clean container works temporarily*\n"
            "- [ ] 7. Nitrile work gloves & eye protection — *dollar store basics*\n\n"
            "[chips: Starting failure scan | Brake system check | Acoustic noise scan]\n\n"
            "💡 **Budget tip:** Many campus workshops offer tool libraries for enrolled students. Ask your department coordinator!"
        )

    # 12. General Motorcycle Systems Briefings
    general_responses = {
        ('oil', 'engine oil', 'oil change'): (
            f"Engine lubrication protocol, {sir}:\n\n"
            "- [ ] 1. Warm engine 3 minutes, then shut off and keep bike upright.\n"
            "- [ ] 2. Inspect sight glass or clean dipstick: oil should sit between MIN and MAX marks.\n"
            "- [ ] 3. Place drain pan below crankcase; remove drain bolt (replace crush washer upon reassembly).\n"
            "- [ ] 4. Replace spin-on or cartridge oil filter and torque to manufacturer specification.\n"
            "- [ ] 5. Refill with recommended JASO-MA2 motorcycle 4T oil (do not use car oil with friction modifiers).\n\n"
            f"💡 **Student savings:** Buy oil in 1-gallon containers (cheaper per quart). Share with a riding buddy to split costs.\n"
            "[chips: Smoke near engine casing & sprocket | How many parts | Starting failure scan]"
        ),
        ('battery', 'car battery', 'dead battery', 'battery diagnostic'): (
            f"Power-cell diagnostics, {sir}:\n\n"
            "• Healthy battery reads **12.6V+** at rest\n"
            "• At **12.0V or below**, battery is 75% discharged\n"
            "• Cranking voltage must not fall below **9.6V**\n"
            "• Typical motorcycle AGM/Lithium battery lifespan: 3–5 years\n\n"
            f"💡 **Student tip:** If battery is weak, try jump-starting from a car (60 seconds max) or borrow a portable jump pack from the campus safety office.\n"
            "[chips: Rapid clicking sound | Cranks slowly but won't start | Where is the main fuse?]"
        ),
        ('tyre', 'tire', 'flat tyre', 'flat tire'): (
            f"Tyre safety protocol, {sir}:\n\n"
            "- [ ] 1. Check cold tyre pressure weekly (typically 29–33 PSI front, 33–36 PSI rear).\n"
            "- [ ] 2. Inspect tread depth indicators — replace if tread is under 1.6 mm.\n"
            "- [ ] 3. Check for cracks, dry rot on sidewalls, or embedded nails/screws.\n"
            "- [ ] 4. Inspect wheel valve stem rubber for weathering or leakage.\n\n"
            f"💡 **Student tip:** Many tire shops offer 'free air' for air pressure checks if you're buying fuel. Build a relationship with a local shop!\n"
            "[chips: Brake system check | Starting failure scan | Help & capabilities]"
        ),
        ('coolant', 'overheating', 'temperature', 'radiator'): (
            f"Thermal cooling protocol, {sir}:\n\n"
            "- [ ] 1. Never open radiator cap while engine is warm (extreme scald hazard).\n"
            "- [ ] 2. Inspect radiator cooling fins for dirt or bent aluminum fins.\n"
            "- [ ] 3. Verify radiator electric fan triggers when engine temperature rises.\n"
            "- [ ] 4. Check coolant expansion reservoir level between LOW and FULL lines.\n\n"
            f"💡 **Student tip:** If coolant leaks, water (distilled) can be a temporary emergency fix to get to school — but replace with proper coolant ASAP.\n"
            "[chips: White sweet-smelling smoke | Engine oil check | Starting failure scan]"
        ),
        ('transmission', 'gearbox', 'gear', 'clutch'): (
            f"Drivetrain protocol, {sir}:\n\n"
            "- [ ] 1. Check clutch cable free play (2-3 mm at handlebar perch).\n"
            "- [ ] 2. Inspect shift lever linkage rod and ball joints for excess play.\n"
            "- [ ] 3. If clutch slips under acceleration: check cable binding or friction plate wear.\n\n"
            f"💡 **Student tip:** If cable adjuster is broken, zip-tie or bailing wire can temporarily set clutch free ride until you can order a replacement online.\n"
            "[chips: Engine oil check | Starting failure scan | List all parts]"
        ),
        ('spark plug', 'ignition', 'misfire'): (
            f"Ignition protocol, {sir}:\n\n"
            "- [ ] 1. Remove spark plug using dedicated rubber-lined plug socket.\n"
            "- [ ] 2. Inspect electrode color: light tan/grey is optimal; black soot indicates rich mixture; blistered white indicates lean.\n"
            "- [ ] 3. Measure electrode gap using wire feeler gauge (typically 0.7–0.8 mm).\n"
            "- [ ] 4. Clean electrode with brass wire brush or replace with fresh NGK plug.\n\n"
            f"💡 **Student tip:** If plug is fouled, remove and soak in carb cleaner bath (recovered from parts cleaning) instead of buying new — often works for one more season.\n"
            "[chips: Cranks normally, no combustion | Black smoke from exhaust | Starting failure scan]"
        ),
    }

    for keywords, response in general_responses.items():
        if any(k in msg for k in keywords):
            return response

    if any(k in msg for k in ['thank', 'thanks', 'bye', 'goodbye', 'see you']):
        return (
            f"Always a pleasure, {sir}. I shall remain on standby. "
            "Safe riding, and do not hesitate to run another scan whenever needed.\n\n"
            "[chips: Starting failure scan | Brake system check | Acoustic noise scan]"
        )

    # 13. Fallback with helpful interactive chips
    return (
        f"I'm afraid I didn't recognize that specific phrasing, {sir}. "
        "Select a diagnostic category below, or describe the symptom:\n\n"
        "[chips: Engine won't start | Spongy brakes | Strange engine noise | Smoke from exhaust | "
        "Battery dead | Oil change | Tyre check | Coolant leak | Spark plug foul | Clutch adjustment | "
        "List all symptoms | List all parts | Help & capabilities]"
    )


@login_required(login_url='login')
@require_http_methods(['POST'])
def jarvis_chat(request):
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid request'}, status=400)

    if not message:
        return JsonResponse({'error': 'Empty message'}, status=400)

    if len(message) > 1000:
        return JsonResponse({'error': 'Message too long (max 1000 chars)'}, status=400)

    reply = _jarvis_response(message, request.user)
    return JsonResponse({'reply': reply})
