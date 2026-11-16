import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from apps.core import views
from apps.core.guided_diagnostic import handle_guided_turn, start_state, resolve_profile
from apps.core.services.intake import missing_vehicle_questions

@pytest.fixture
def auth_user(db):
    user, _ = User.objects.get_or_create(username='engine_tester', defaults={'first_name': 'Juan'})
    return user


def test_extract_various_engine_displacements():
    """Verify that Jarvis accurately extracts various engine sizes (125, 150, 250, etc.)."""
    info1 = views._extract_vehicle_info("how to fix problem in 150cc engine")
    assert info1['displacement'] == '150CC'

    info2 = views._extract_vehicle_info("i have a 125 engine that sputters")
    assert info2['displacement'] == '125CC'

    info3 = views._extract_vehicle_info("250cc engine repair guide")
    assert info3['displacement'] == '250CC'

    info4 = views._extract_vehicle_info("motorcycle is 400cc and running hot")
    assert info4['displacement'] == '400CC'


def test_engine_fix_missing_fuel_asks_carb_vs_fi(auth_user):
    """When a user asks how to fix an engine part and fuel system is missing, Jarvis must ask Carb vs FI and explain why."""
    with patch('apps.core.views._jarvis_gemini', return_value=None), \
         patch('apps.core.diagnostic_engine.call_configured_ai', return_value=None):
        reply = views._jarvis_response("how to fix this in the 150 engine", auth_user, history=[])
    
    reply_lower = reply.lower()
    # Must ask Carb vs FI
    assert "carbureted (carb)" in reply_lower or "carburetor" in reply_lower or "carb" in reply_lower
    assert "fuel-injected (fi)" in reply_lower or "fi" in reply_lower
    # Must explain that Carb and FI are very different in tools / diagnostics
    assert "different" in reply_lower or "tools" in reply_lower or "diagnostics" in reply_lower
    # Must offer chips
    assert "[chips:" in reply
    assert "Carburetor (Carb)" in reply
    assert "Fuel-Injected (FI)" in reply


def test_engine_fix_carburetor_protocol(auth_user):
    """When fuel system is Carburetor, Jarvis provides Carb-specific tools, common faults, and checklist."""
    msg = "how to fix this in the 150cc engine (Carburetor)"
    with patch('apps.core.views._jarvis_gemini', return_value=None), \
         patch('apps.core.diagnostic_engine.call_configured_ai', return_value=None):
        reply = views._jarvis_response(msg, auth_user, history=[])
    
    reply_lower = reply.lower()
    # Carb tools and parts
    assert any(w in reply_lower for w in ["screwdriver", "carb cleaner", "jet"])
    assert any(w in reply_lower for w in ["pilot jet", "main jet", "float bowl", "mixture screw"])
    assert "- [ ]" in reply


def test_engine_fix_fi_protocol(auth_user):
    """When fuel system is FI, Jarvis provides FI-specific tools, common faults, and checklist."""
    msg = "how to fix this in the 250cc engine (FI)"
    with patch('apps.core.views._jarvis_gemini', return_value=None), \
         patch('apps.core.diagnostic_engine.call_configured_ai', return_value=None):
        reply = views._jarvis_response(msg, auth_user, history=[])
    
    reply_lower = reply.lower()
    # FI tools and parts
    assert any(w in reply_lower for w in ["multimeter", "pressure gauge", "fuel pump", "injector"])
    assert any(w in reply_lower for w in ["pump", "voltage", "throttle body", "ecu"])
    assert "- [ ]" in reply


def test_difference_between_carb_and_fi(auth_user):
    """Direct query about the difference between Carb and FI explains tools, diagnostics, and failure modes."""
    with patch('apps.core.views._jarvis_gemini', return_value=None), \
         patch('apps.core.diagnostic_engine.call_configured_ai', return_value=None):
        reply = views._jarvis_response("what is the difference between carb and fi?", auth_user, history=[])
    
    reply_lower = reply.lower()
    assert "tools" in reply_lower
    assert "diagnostic" in reply_lower
    assert "carburetor" in reply_lower
    assert "fuel-injected" in reply_lower


def test_guided_diagnostic_prompts_fuel_when_missing():
    """In guided diagnostic, diagnosing starting or power issues prompts Carb vs FI if unconfirmed."""
    state = start_state()
    # Step 1: User specifies an unknown bike model or generic backbone where fuel varies
    state['stage'] = 'type'
    reply = handle_guided_turn("standard backbone motorcycle with engine problem", None, [], state)
    
    # Needs fuel confirmed
    if 'Carb' in reply or 'carb' in reply.lower():
        assert 'fuel-injected' in reply.lower() or 'fi' in reply.lower()
    
    # Test fuel response advances state
    state['stage'] = 'fuel'
    state['bike'] = resolve_profile({'make': 'Honda', 'model': 'TMX 125'})
    reply2 = handle_guided_turn("Carburetor", None, [], state)
    assert state.get('fuel_confirmed') is True
    assert state['bike']['fuel'] == 'Carburetor'


def test_missing_vehicle_questions_includes_fuel_and_disp():
    """Intake questions helper must detect missing fuel system and displacement."""
    veh = {'make': 'Honda', 'model': 'CRF', 'year': '2022', 'vehicle_type': 'dual-sport'}
    questions = missing_vehicle_questions(veh)
    q_texts = [q['question'].lower() for q in questions]
    assert any('carbureted' in qt or 'carb' in qt for qt in q_texts)
    assert any('displacement' in qt or 'engine size' in qt or 'cc' in qt for qt in q_texts)
