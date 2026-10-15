import os
import django
import json
import pytest

os.environ['DJANGO_SETTINGS_MODULE'] = 'mysite.settings'
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from apps.core.views import _jarvis_response, _detect_language, _extract_vehicle_info

User = get_user_model()


@pytest.fixture
def auth_user(db):
    user, _ = User.objects.get_or_create(
        username='mechanic_tester',
        defaults={'first_name': 'Tony', 'email': 'tony@stark.com'}
    )
    return user


def test_language_detection():
    # English
    assert _detect_language("My front brake is soft and spongy") == 'english'
    # Tagalog
    assert _detect_language("Kamusta, ayaw mag-start ng motor ko at malambot ang preno") == 'tagalog'
    # Hiligaynon
    assert _detect_language("Maayong adlaw, indi mag-andar ang akon motor kag humok ang preno") == 'hiligaynon'


def test_vehicle_extraction_from_history():
    history = [
        {'role': 'user', 'text': 'My front brake is not working'},
        {'role': 'bot', 'text': 'What motorcycle or car do you have?'},
        {'role': 'user', 'text': "It's a 2022 Honda Click 125i with disc brake."},
    ]
    info = _extract_vehicle_info("lever feels soft", history=history)
    assert info['make'] == 'Honda'
    assert 'Click' in info['model']
    assert info['year'] == '2022'
    assert info['brake_type'] == 'disc'


def test_brake_intake_when_unspecified(auth_user):
    """When vehicle details are omitted, JARVIS must ask intake questions, provide intake form, and warn about safety."""
    from unittest.mock import patch
    with patch('apps.core.views._jarvis_gemini', return_value=None):
        response = _jarvis_response("My front brake is not working", auth_user, history=[])
    
    # Must ask intake questions (make/model/year, disc vs drum)
    resp_lower = response.lower()
    assert any(k in resp_lower for k in ['model', 'make', 'brand'])
    assert "year" in resp_lower
    assert "disc" in resp_lower and "drum" in resp_lower
    
    # Must include mandatory safety rule
    assert "do not ride or drive" in resp_lower or "safety warning" in resp_lower
    assert any(w in resp_lower for w in ["qualified mechanic", "mechanic", "traffic"])
    
    # Must include action chips and vehicle form
    assert "[chips:" in response
    assert "[vehicle-form:" in response


def test_brake_multi_turn_remembers_vehicle(auth_user):
    """Turn 2: Once vehicle is supplied, JARVIS remembers the vehicle and advances diagnosis."""
    history = [
        {'role': 'user', 'text': 'My front brake is not working'},
        {'role': 'bot', 'text': "Let's identify your vehicle first. What is the make and model? [chips: Disc | Drum]"},
    ]
    turn2_input = "It's a 2022 Honda Click 125i. The front brake lever feels soft and spongy."
    response = _jarvis_response(turn2_input, auth_user, history=history)
    
    resp_lower = response.lower()
    # Should acknowledge vehicle or proceed to hydraulic disc diagnosis
    assert any(w in resp_lower for w in ["honda", "click", "2022", "hydraulic", "disc"])
    # Should NOT ask again "what is the make" or "what is the brand"
    assert "what is the make" not in resp_lower and "what is the brand" not in resp_lower
    # Must maintain safety warning
    assert "safety" in resp_lower or "caution" in resp_lower
    # Action chips present
    assert "[chips:" in response


def test_engine_no_start_intake(auth_user):
    """Engine no-start inquiry should systematically isolate starter, battery, fuel, or ignition and provide intake form."""
    from unittest.mock import patch
    with patch('apps.core.views._jarvis_gemini', return_value=None):
        response = _jarvis_response("My motorcycle won't start", auth_user, history=[])
    resp_lower = response.lower()
    assert any(w in resp_lower for w in ["make", "brand", "model"])
    assert any(w in resp_lower for w in ["starter", "crank", "turn over"])
    assert "[chips:" in response
    assert "[vehicle-form:" in response


def test_overheating_scald_safety_warning(auth_user):
    """Engine overheating protocol must explicitly warn never to open a hot radiator cap."""
    response = _jarvis_response("My engine is overheating", auth_user, history=[])
    resp_lower = response.lower()
    assert "radiator cap" in resp_lower
    assert any(w in resp_lower for w in ["scald", "hot", "burn"])
    assert "[chips:" in response


def test_multilingual_tagalog_intake(auth_user):
    """When spoken to in Tagalog, JARVIS responds in Tagalog."""
    response = _jarvis_response("Kamusta, ayaw mag-start ng motor ko", auth_user, history=[])
    resp_lower = response.lower()
    assert any(w in resp_lower for w in ['sasakyan', 'makina', 'starter', 'baterya', 'kamusta', 'araw'])
    assert "[chips:" in response
    assert "[vehicle-form:" in response


def test_multilingual_hiligaynon_intake(auth_user):
    """When spoken to in Hiligaynon, JARVIS responds in Hiligaynon."""
    response = _jarvis_response("Maayong adlaw, indi mag-andar ang akon motor", auth_user, history=[])
    resp_lower = response.lower()
    assert any(w in resp_lower for w in ['salakyan', 'makina', 'starter', 'baterya', 'maayong', 'preno', 'andar'])
    assert "[chips:" in response
    assert "[vehicle-form:" in response


def test_jarvis_chat_api_endpoint(client, auth_user):
    """Verify POST /jarvis/chat/ processes multi-turn history and returns reply with quota details."""
    client.force_login(auth_user)
    payload = {
        'message': 'spongy brakes',
        'history': [
            {'role': 'user', 'text': '2022 Honda Click 125i'},
        ]
    }
    res = client.post(
        '/jarvis/chat/',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert res.status_code == 200
    data = res.json()
    assert 'reply' in data
    assert 'quota' in data
    assert 'percent_left' in data['quota']
    assert 'tokens_today' in data['quota']


def test_form_submission_with_full_details(auth_user):
    """Submitting full vehicle info form directly isolates the symptom without extra questions."""
    from unittest.mock import patch
    form_msg = "Vehicle: 2022 Honda Click 125i (Scooter, 125cc, Fuel-injected). Symptom: Rapid clicking sound when pressing the starter button."
    with patch('apps.core.views._jarvis_gemini', return_value=None):
        response = _jarvis_response(form_msg, auth_user, history=[])
    resp_lower = response.lower()
    # Must immediately identify relay chatter
    assert any(w in resp_lower for w in ["solenoid", "relay", "chatter", "clicking"])
    # Must provide checklist
    assert "- [ ]" in response
    # Must not ask what is the make or model
    assert "what is the brand" not in resp_lower and "what is the make" not in resp_lower


def test_form_submission_with_custom_vehicle_model(auth_user):
    """Users can enter unlisted or custom vehicle models and have them recognized."""
    from unittest.mock import patch
    form_msg = "Vehicle: 2021 Kymco Like 150i (Scooter, 150cc, Fuel-injected). Symptom: Engine cranks normally but will not start."
    with patch('apps.core.views._jarvis_gemini', return_value=None):
        response = _jarvis_response(form_msg, auth_user, history=[])
    resp_lower = response.lower()
    # Must diagnose combustion triangle (spark, fuel, compression)
    assert any(w in resp_lower for w in ["combustion", "spark", "fuel"])
    assert "- [ ]" in response


def test_form_submission_with_partial_details(auth_user):
    """Partial info (e.g. displacement omitted, fuel Not sure) is accepted gracefully."""
    from unittest.mock import patch
    form_msg = "Vehicle: Yamaha Aerox (Scooter, Not sure). Symptom: Engine starts briefly, then shuts off immediately."
    with patch('apps.core.views._jarvis_gemini', return_value=None):
        response = _jarvis_response(form_msg, auth_user, history=[])
    resp_lower = response.lower()
    # Must diagnose starts then dies (Option E)
    assert any(w in resp_lower for w in ["sustenance", "starts then dies", "idle", "starvation"])
    assert "- [ ]" in response


def test_symptom_starter_does_not_respond_lights_work(auth_user):
    """Option F: Starter not responding but dash lights on isolates safety interlock."""
    from unittest.mock import patch
    form_msg = "Vehicle: 2020 Honda Beat (Scooter). Symptom: Starter does not respond, but dashboard lights work."
    with patch('apps.core.views._jarvis_gemini', return_value=None):
        response = _jarvis_response(form_msg, auth_user, history=[])
    resp_lower = response.lower()
    # Must check safety switches / interlock
    assert any(w in resp_lower for w in ["interlock", "safety switch", "brake lever", "side-stand", "button"])
    assert "- [ ]" in response

