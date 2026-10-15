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
    Rule-based J.A.R.V.I.S. engine.
    Speaks like Tony Stark's assistant while answering from the motor database.
    """
    from apps.motor.models import DiagnosticSymptom, Part, TroubleshootingGuide

    msg = message.lower().strip()
    sir = _jarvis_address(user)

    greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy']
    if any(msg.startswith(g) for g in greetings):
        return (
            f"At your service, {sir}. J.A.R.V.I.S. online. Systems nominal. "
            "I can run diagnostics, retrieve troubleshooting protocols, look up parts, "
            "and advise on the motorcycle. How may I assist?"
        )

    if any(k in msg for k in ['who are you', 'what are you', 'your name', 'introduce yourself']):
        return (
            f"I am J.A.R.V.I.S., Just A Rather Very Intelligent System. "
            f"I was built to keep this workshop running, {sir}: diagnose faults, "
            "pull repair guides, catalogue parts, and offer a second opinion before you pick up a wrench. "
            "Shall we begin?"
        )

    if any(k in msg for k in ['help', 'what can you do', 'capabilities', 'commands']):
        return (
            f"Of course, {sir}. My current protocols include:\n\n"
            "• **Symptom scan** — describe the noise, leak, or behaviour\n"
            "• **Repair protocol** — ask how to fix a known issue\n"
            "• **Parts inventory** — ask what you need, or say 'list all parts'\n"
            "• **Archive stats** — 'how many symptoms', 'how many parts'\n"
            "• **General systems** — oil, brakes, battery, tyres, cooling, ignition\n\n"
            "Speak naturally. I shall do the rest."
        )

    if any(k in msg for k in ['how many symptoms', 'total symptoms', 'count symptoms']):
        count = DiagnosticSymptom.objects.count()
        return (
            f"I've queried the diagnostic archive, {sir}. "
            f"There are currently **{count}** known symptoms on file."
        )

    if any(k in msg for k in ['how many parts', 'total parts', 'count parts']):
        count = Part.objects.count()
        return (
            f"Parts catalogue reports **{count}** entries, {sir}."
        )

    if any(k in msg for k in ['how many guides', 'total guides', 'troubleshooting count']):
        count = TroubleshootingGuide.objects.count()
        return (
            f"I have **{count}** troubleshooting protocols ready, {sir}."
        )

    if any(k in msg for k in ['list symptoms', 'show symptoms', 'all symptoms', 'symptoms list']):
        symptoms = DiagnosticSymptom.objects.values_list('symptom_name', flat=True)[:20]
        if symptoms:
            symptom_list = '\n'.join(f"• {s}" for s in symptoms)
            return (
                f"Pulling the symptom index now, {sir}:\n\n{symptom_list}"
            )
        return f"The diagnostic archive is empty, {sir}. Nothing on file yet."

    if any(k in msg for k in ['list parts', 'show parts', 'all parts', 'parts list']):
        parts = Part.objects.values('part_name', 'category', 'estimated_cost')[:20]
        if parts:
            parts_list = '\n'.join(
                f"• {p['part_name']} ({p['category'] or 'General'}) — ${p['estimated_cost']}"
                for p in parts
            )
            return f"Here is the parts inventory, {sir}:\n\n{parts_list}"
        return f"No parts are catalogued yet, {sir}."

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
            f"Scan complete, {sir}. I have a match: **{matched_symptom.symptom_name}** "
            f"(category: {matched_symptom.category}).\n"
        ]

        if matched_symptom.description:
            response_lines.append(f"**Briefing:** {matched_symptom.description}\n")

        if guides:
            response_lines.append("**Recommended protocol:**\n")
            for i, guide in enumerate(guides, 1):
                response_lines.append(f"{i}. **Likely cause:** {guide.possible_cause}")
                response_lines.append(f"   **Instructions:** {guide.repair_instructions}")
                if guide.advice_notes:
                    response_lines.append(f"   **Caution:** {guide.advice_notes}")
                required_parts = guide.required_parts.all()
                if required_parts:
                    parts_str = ', '.join(
                        f"{rp.part.part_name} (×{rp.quantity_needed})"
                        for rp in required_parts
                    )
                    response_lines.append(f"   **Required parts:** {parts_str}")
                response_lines.append("")
            response_lines.append("Shall I walk you through the first step?")
        else:
            response_lines.append(
                "I have the symptom on file, but no repair protocol is linked yet. "
                "A qualified mechanic would be the prudent next call."
            )

        return '\n'.join(response_lines)

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

            return '\n'.join(lines)

    general_responses = {
        ('oil', 'engine oil', 'oil change'): (
            f"Engine lubrication briefing, {sir}:\n"
            "• Change oil every 5,000–10,000 km depending on grade\n"
            "• Check the sight glass or dipstick monthly\n"
            "• Low oil pressure — stop the engine immediately\n"
            "• Use the manufacturer-specified viscosity. I do not recommend improvising."
        ),
        ('battery', 'car battery', 'dead battery'): (
            f"Power-cell diagnostics, {sir}:\n"
            "• A healthy battery reads 12.6V at rest\n"
            "• Below 12.0V, it wants charging, or replacing\n"
            "• Slow cranking, dim lights, a click instead of a start: classic failure mode\n"
            "• Typical lifespan: 3–5 years"
        ),
        ('brake', 'brakes', 'braking'): (
            f"Braking system, {sir}. Rather important, that:\n"
            "• Squeal usually means worn pads\n"
            "• Grinding is metal on metal. Replace at once\n"
            "• A soft pedal may mean air in the lines or a leak\n"
            "• Vibration under braking often points to warped discs"
        ),
        ('tyre', 'tire', 'flat tyre', 'flat tire'): (
            f"Tyre briefing, {sir}:\n"
            "• Check pressure monthly, typically 30-35 PSI, confirm on the sidewall\n"
            "• Tread below 1.6 mm: replace immediately\n"
            "• Rotate every 8,000–12,000 km\n"
            "• Vibration at speed may be imbalance, not the engine"
        ),
        ('coolant', 'overheating', 'temperature', 'radiator'): (
            f"Thermal systems, {sir}:\n"
            "• Overheating can destroy an engine. Pull over safely\n"
            "• Check coolant only when the engine is cold\n"
            "• Flush every two years, or as the manufacturer specifies\n"
            "• White exhaust smoke may indicate coolant in the combustion chamber. That is not a good day."
        ),
        ('transmission', 'gearbox', 'gear'): (
            f"Drivetrain notes, {sir}:\n"
            "• Slipping, delayed engagement, or harsh shifts warrant inspection\n"
            "• Fluid should be red or pink — brown means it has had a long, unhappy life\n"
            "• Service interval is typically 60,000–100,000 km\n"
            "• A burning smell from below: fluid, and urgency"
        ),
        ('alternator', 'charging', 'charge'): (
            f"Charging system, {sir}:\n"
            "• Battery warning lamp on: the alternator may have retired early\n"
            "• Healthy output: 13.7–14.7V with the engine running\n"
            "• Dim lights and a repeatedly dead battery are the usual calling cards"
        ),
        ('spark plug', 'ignition', 'misfire'): (
            f"Ignition briefing, {sir}:\n"
            "• Misfire, rough idle, or poor economy: inspect the plugs\n"
            "• Standard plugs: about every 30,000 km\n"
            "• Iridium or platinum: around 100,000 km\n"
            "• A fouled plug will make starting theatrical, and not in a good way"
        ),
    }

    for keywords, response in general_responses.items():
        if any(k in msg for k in keywords):
            return response

    if any(k in msg for k in ['thank', 'thanks', 'bye', 'goodbye', 'see you']):
        return (
            f"Always a pleasure, {sir}. I shall remain on standby. "
            "Do try not to ignore the warning lights."
        )

    return (
        f"I'm afraid that isn't in my current dataset, {sir}. Try asking about:\n\n"
        "• A symptom: engine knocking, oil leak, smoke\n"
        "• A part: brake pads, alternator, seals\n"
        "• A system: overheating, battery, tyres\n"
        "• Or say **help** and I shall list my protocols."
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
