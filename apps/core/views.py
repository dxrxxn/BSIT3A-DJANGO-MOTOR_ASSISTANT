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

def _jarvis_response(message, user):
    """
    Rule-based AI engine for Jarvis.
    Queries the database for context-aware motor diagnostics answers.
    """
    from apps.motor.models import DiagnosticSymptom, Part, TroubleshootingGuide

    msg = message.lower().strip()

    # Greetings
    greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy']
    if any(msg.startswith(g) for g in greetings):
        name = user.first_name or user.username
        return (
            f"Hello {name}! I'm Jarvis, your Motor Assistant AI. "
            "I can help you with diagnostic symptoms, troubleshooting guides, parts information, "
            "and general motor questions. What can I help you with today?"
        )

    # Identity
    if any(k in msg for k in ['who are you', 'what are you', 'your name', 'introduce yourself']):
        return (
            "I'm Jarvis — your intelligent Motor Assistant AI. "
            "I'm built into this dashboard to help you diagnose vehicle issues, "
            "find troubleshooting guides, look up parts, and answer motor-related questions. "
            "Just ask me anything!"
        )

    # Help / capabilities
    if any(k in msg for k in ['help', 'what can you do', 'capabilities', 'commands']):
        return (
            "Here's what I can do for you:\n\n"
            "• **Symptom lookup** — Ask about any symptom (e.g. 'engine knocking')\n"
            "• **Troubleshooting guides** — Ask 'how to fix [symptom]'\n"
            "• **Parts info** — Ask 'what parts do I need for [issue]' or 'list all parts'\n"
            "• **Stats** — Ask 'how many symptoms', 'how many parts'\n"
            "• **General motor questions** — Oil, brakes, battery, tires, etc.\n\n"
            "Just type naturally and I'll do my best to help!"
        )

    # Stats queries
    if any(k in msg for k in ['how many symptoms', 'total symptoms', 'count symptoms']):
        count = DiagnosticSymptom.objects.count()
        return f"There are currently **{count} diagnostic symptoms** in the system."

    if any(k in msg for k in ['how many parts', 'total parts', 'count parts']):
        count = Part.objects.count()
        return f"There are currently **{count} parts** in the parts database."

    if any(k in msg for k in ['how many guides', 'total guides', 'troubleshooting count']):
        count = TroubleshootingGuide.objects.count()
        return f"There are currently **{count} troubleshooting guides** available."

    # List all symptoms
    if any(k in msg for k in ['list symptoms', 'show symptoms', 'all symptoms', 'symptoms list']):
        symptoms = DiagnosticSymptom.objects.values_list('symptom_name', flat=True)[:20]
        if symptoms:
            symptom_list = '\n'.join(f"• {s}" for s in symptoms)
            return f"Here are the diagnostic symptoms I know about:\n\n{symptom_list}"
        return "No diagnostic symptoms found in the database yet."

    # List all parts
    if any(k in msg for k in ['list parts', 'show parts', 'all parts', 'parts list']):
        parts = Part.objects.values('part_name', 'category', 'estimated_cost')[:20]
        if parts:
            parts_list = '\n'.join(
                f"• {p['part_name']} ({p['category'] or 'General'}) — ${p['estimated_cost']}"
                for p in parts
            )
            return f"Here are parts in the database:\n\n{parts_list}"
        return "No parts found in the database yet."

    # Symptom / troubleshooting lookup — search by keyword
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
            f"I found information about **{matched_symptom.symptom_name}** "
            f"(Category: {matched_symptom.category}).\n"
        ]

        if matched_symptom.description:
            response_lines.append(f"**Description:** {matched_symptom.description}\n")

        if guides:
            response_lines.append("**Troubleshooting Guides:**\n")
            for i, guide in enumerate(guides, 1):
                response_lines.append(f"{i}. **Possible Cause:** {guide.possible_cause}")
                response_lines.append(f"   **Instructions:** {guide.repair_instructions}")
                if guide.advice_notes:
                    response_lines.append(f"   **Notes:** {guide.advice_notes}")
                required_parts = guide.required_parts.all()
                if required_parts:
                    parts_str = ', '.join(
                        f"{rp.part.part_name} (×{rp.quantity_needed})"
                        for rp in required_parts
                    )
                    response_lines.append(f"   **Required Parts:** {parts_str}")
                response_lines.append("")
        else:
            response_lines.append("No troubleshooting guides are linked to this symptom yet.")

        return '\n'.join(response_lines)

    # Parts lookup by name
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
                f"**{part.part_name}**\n",
                f"• Part Number: {part.part_number or 'N/A'}",
                f"• Category: {part.category or 'General'}",
                f"• Estimated Cost: ${part.estimated_cost}\n",
            ]

            if guides:
                lines.append("**Used in repairs for:**")
                for g in guides:
                    lines.append(f"• {g.symptom.symptom_name} — {g.possible_cause}")

            return '\n'.join(lines)

    # General motor knowledge
    general_responses = {
        ('oil', 'engine oil', 'oil change'): (
            "**Engine Oil Tips:**\n"
            "• Change oil every 5,000–10,000 km depending on the oil type\n"
            "• Check oil level monthly using the dipstick\n"
            "• Low oil pressure warning = stop the vehicle immediately\n"
            "• Use the manufacturer-recommended viscosity grade"
        ),
        ('battery', 'car battery', 'dead battery'): (
            "**Battery Diagnostics:**\n"
            "• A healthy battery reads 12.6V when fully charged\n"
            "• Below 12.0V means the battery needs charging\n"
            "• Symptoms: slow cranking, dim lights, clicking sound when starting\n"
            "• Average battery lifespan is 3–5 years"
        ),
        ('brake', 'brakes', 'braking'): (
            "**Brake System:**\n"
            "• Squealing brakes often mean worn brake pads\n"
            "• Grinding means metal-on-metal — replace pads immediately\n"
            "• Soft/spongy pedal could indicate air in brake lines or fluid leak\n"
            "• Vibration while braking may mean warped rotors"
        ),
        ('tyre', 'tire', 'flat tyre', 'flat tire'): (
            "**Tyre/Tire Advice:**\n"
            "• Check tyre pressure monthly (usually 30–35 PSI)\n"
            "• Tread depth below 1.6mm — replace immediately\n"
            "• Rotate tyres every 8,000–12,000 km for even wear\n"
            "• Vibration at speed may indicate wheel imbalance"
        ),
        ('coolant', 'overheating', 'temperature', 'radiator'): (
            "**Cooling System:**\n"
            "• Overheating can cause severe engine damage — pull over safely\n"
            "• Check coolant level in the reservoir when the engine is cold\n"
            "• Flush coolant every 2 years or per manufacturer schedule\n"
            "• White smoke from exhaust may mean a coolant leak into the engine"
        ),
        ('transmission', 'gearbox', 'gear'): (
            "**Transmission Tips:**\n"
            "• Slipping gears, delayed engagement, or rough shifts = inspect transmission\n"
            "• Check transmission fluid level and colour (should be red/pink, not brown)\n"
            "• Transmission fluid should be changed every 60,000–100,000 km\n"
            "• Burning smell from under the car = possible transmission fluid issue"
        ),
        ('alternator', 'charging', 'charge'): (
            "**Alternator / Charging System:**\n"
            "• Battery warning light on = alternator may not be charging\n"
            "• A healthy alternator outputs 13.7–14.7V with the engine running\n"
            "• Symptoms of failure: dim lights, dead battery, electrical issues"
        ),
        ('spark plug', 'ignition', 'misfire'): (
            "**Spark Plugs / Ignition:**\n"
            "• Misfires, rough idle, or poor fuel economy = check spark plugs\n"
            "• Standard plugs: replace every 30,000 km\n"
            "• Iridium/platinum plugs: replace every 100,000 km\n"
            "• A fouled plug can cause hard starting and power loss"
        ),
    }

    for keywords, response in general_responses.items():
        if any(k in msg for k in keywords):
            return response

    # Thanks / farewell
    if any(k in msg for k in ['thank', 'thanks', 'bye', 'goodbye', 'see you']):
        return "You're welcome! I'm always here if you need motor diagnostics help. Drive safe! 🚗"

    # Fallback
    return (
        "I'm not sure about that one. Try asking me about:\n\n"
        "• A specific symptom (e.g. 'engine knocking', 'oil leak')\n"
        "• Parts (e.g. 'brake pads', 'alternator')\n"
        "• Common issues (e.g. 'overheating', 'flat tyre', 'battery')\n"
        "• Type **help** to see everything I can do."
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
