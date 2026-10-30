"""Tests for the guided 'identify the bike first' diagnostic flow."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.guided_diagnostic import handle_guided_turn, start_state


def _turn(message, state, history=None):
    return handle_guided_turn(message, None, history or [], state)


def test_first_question_identifies_the_motorcycle():
    state = start_state()
    reply = _turn("my brakes are spongy", state)

    assert state['stage'] == 'identify'
    low = reply.lower()
    assert 'which motorcycle' in low
    assert 'model and year' in low
    assert '[chips:' in reply
    # Safety must still come first.
    assert 'do not ride or drive' in low


def test_after_bike_is_known_it_focuses_and_shows_where_to_look():
    state = start_state()
    history = [{'role': 'user', 'text': 'my brakes are spongy'}]
    reply = _turn("2022 Honda Click 125i", state, history)
    low = reply.lower()

    assert state['stage'] == 'narrow'
    assert state['area'] == 'brakes'
    assert 'focus vehicle' in low
    assert 'honda click 125i' in low
    # Free inspection points, not parts-first.
    assert 'where to look first' in low
    assert 'brake fluid' in low
    assert '2 mm' in low
    assert '[chips:' in reply
    # Concise: three one-line checks, no Good/Bad essays or duplicate
    # option bullets that repeat the chips.
    numbered = [ln for ln in reply.splitlines() if ln.strip() and ln.strip()[0].isdigit()]
    assert len(numbered) == 3
    assert 'good:' not in low and 'bad:' not in low
    assert not any(ln.strip().startswith('- ') for ln in reply.splitlines())


def test_front_brake_shortcut_still_shows_the_safety_alert():
    state = start_state()
    reply = _turn("Front brake not working", state)

    low = reply.lower()
    assert 'do not ride or drive' in low
    assert 'which motorcycle' in low


def test_model_only_chip_asks_for_year_before_checks():
    state = start_state()
    reply = _turn("Click 125i", state)
    low = reply.lower()

    assert state['stage'] == 'year'
    assert 'what year' in low
    assert 'click 125i' in low
    assert '[chips:' in reply

    reply = _turn("2022", state)
    low = reply.lower()
    assert state['stage'] == 'area'
    assert '2022 honda click 125i' in low
    assert 'what is the problem' in low


def test_year_can_be_skipped_without_blocking_the_flow():
    state = start_state()
    _turn("Click 125i", state)
    reply = _turn("Not sure", state)
    low = reply.lower()

    assert state['stage'] == 'area'
    assert 'honda click 125i' in low
    assert 'what is the problem' in low


def test_year_question_keeps_brake_safety_first():
    state = start_state()
    reply = _turn("Honda Click 125i, front brake is soft", state)
    low = reply.lower()

    assert state['stage'] == 'year'
    assert 'do not ride or drive' in low
    assert 'what year' in low


def test_brake_area_chip_shows_the_critical_alert():
    state = start_state()
    _turn("2022 Honda Click 125i", state)
    reply = _turn("Brakes", state)
    low = reply.lower()

    assert 'do not ride or drive' in low
    assert 'where to look first' in low


def test_answering_questions_narrows_to_a_verdict():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'front brake is soft'}])

    # First narrowing answer: spongy lever.
    reply = _turn("it feels spongy", state)
    assert state['answers'].get('brake_symptom') == 'spongy'

    # Second answer: fluid is fine.
    reply = _turn("fluid is above min and clear", state)
    assert state['stage'] == 'verdict'

    reply = _turn("ok", state)
    low = reply.lower()
    assert 'most likely cause' in low
    assert 'air' in low  # air in the hydraulic line
    assert 'free' in low
    assert '[chips:' in reply


def test_not_sure_bike_falls_back_to_type():
    state = start_state()
    reply = _turn("not sure", state)
    assert state['stage'] == 'type'
    assert 'what type of motorcycle' in reply.lower()

    reply = _turn("scooter", state)
    assert state['stage'] == 'area'
    assert 'focus vehicle' in reply.lower()


def test_start_over_resets_the_flow():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'brakes are soft'}])
    reply = _turn("start over", state)
    assert state['stage'] == 'identify'
    assert 'which motorcycle' in reply.lower()


def test_fixed_answer_closes_the_session():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'brakes are soft'}])
    _turn("spongy", state)
    _turn("above min", state)
    reply = _turn("it worked, thanks", state)
    assert state['stage'] == 'done'
    assert 'back in service' in reply.lower()


def test_still_not_fixed_reopens_the_checks_instead_of_closing():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'brakes are soft'}])
    _turn("spongy", state)
    _turn("above min", state)
    reply = _turn("still not fixed", state)
    assert state['stage'] == 'narrow'
    assert 'where to look first' in reply.lower()


def test_show_another_check_returns_to_the_checklist():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'brakes are soft'}])
    _turn("spongy", state)
    _turn("above min", state)
    reply = _turn("Show another check", state)
    assert state['stage'] == 'narrow'
    assert 'where to look first' in reply.lower()


def test_exact_chip_labels_map_to_the_right_option():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'engine will not start'}])
    # Click the chip labels verbatim.
    _turn("Completely dead - no dashboard lights", state)
    reply = _turn("Havent checked yet", state)
    low = reply.lower()
    assert 'no power reaching the starter' in low
    assert 'free' in low


def test_starting_click_verdict_points_at_battery_or_relay():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'engine will not start'}])
    _turn("Rapid clicking / relay chatter", state)
    reply = _turn("Havent checked yet", state)
    low = reply.lower()
    assert 'relay' in low and 'battery' in low


def test_overheat_with_dead_fan_finds_the_fan_circuit():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'engine overheating'}])
    _turn("In traffic or at idle", state)
    reply = _turn("No, it never spins", state)
    low = reply.lower()
    assert 'radiator fan' in low
    assert 'fuse' in low


def test_bottom_end_knock_tells_the_user_to_stop_the_engine():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'strange engine noise'}])
    _turn("Deep inside / bottom of the engine", state)
    reply = _turn("All the time", state)
    low = reply.lower()
    assert 'stop the engine' in low or 'shut the engine off' in low


def test_current_bike_overrides_an_old_bike_in_history():
    state = start_state()
    history = [
        {'role': 'user', 'text': 'I have a 2022 Honda Click 125i, brakes are weak'},
        {'role': 'bot', 'text': 'Focus vehicle: 2022 Honda Click 125i - scooter, CVT belt'},
    ]
    reply = _turn("Yamaha Mio 2019, engine overheating", state, history)
    assert 'Mio' in reply
    assert 'Click' not in reply


def test_fresh_session_does_not_inherit_a_bike_from_old_chat_log():
    state = start_state()
    history = [{'role': 'user', 'text': 'my 2022 Honda Click 125i brakes are weak'}]
    reply = _turn("my brakes are weak", state, history)
    assert state['stage'] == 'identify'


def test_tagalog_guided_flow_is_localized():
    state = start_state()
    reply = handle_guided_turn("malambot ang preno ng motor ko", None, [], state, lang='tagalog')
    assert 'anong motor' in reply.lower()

    reply = handle_guided_turn(
        "2022 Honda Click 125i", None,
        [{'role': 'user', 'text': 'malambot ang preno'}], state, lang='tagalog'
    )
    low = reply.lower()
    assert 'pokus na motor' in low
    assert 'saan titingin' in low


@pytest.mark.django_db
def test_chat_endpoint_keeps_the_guided_state_in_session():
    user = get_user_model().objects.create_user(
        username='guided', password='secret1234', first_name='Alex'
    )
    client = _client()
    client.force_login(user)

    with patch('apps.core.views._get_gemini_client', return_value=None):
        r1 = client.post(
            reverse('jarvis_chat'),
            data='{"message": "my front brake is soft"}',
            content_type='application/json',
        )
        assert r1.status_code == 200
        body1 = r1.json()['reply']
        assert 'which motorcycle' in body1.lower()

        r2 = client.post(
            reverse('jarvis_chat'),
            data='{"message": "2022 Honda Click 125i", "history": [{"role": "user", "text": "my front brake is soft"}]}',
            content_type='application/json',
        )
        assert r2.status_code == 200
        body2 = r2.json()['reply']
        assert 'focus vehicle' in body2.lower()
        assert 'where to look first' in body2.lower()

    session = client.session
    assert session['jarvis_guided']['stage'] == 'narrow'
    assert session['jarvis_guided']['area'] == 'brakes'


@pytest.mark.django_db
def test_reset_flag_clears_the_guided_state():
    user = get_user_model().objects.create_user(
        username='resetter', password='secret1234', first_name='Alex'
    )
    client = _client()
    client.force_login(user)

    with patch('apps.core.views._get_gemini_client', return_value=None):
        client.post(
            reverse('jarvis_chat'),
            data='{"message": "my front brake is soft"}',
            content_type='application/json',
        )
        client.post(
            reverse('jarvis_chat'),
            data='{"message": "2022 Honda Click 125i"}',
            content_type='application/json',
        )
        assert 'jarvis_guided' in client.session

        resp = client.post(
            reverse('jarvis_chat'),
            data='{"reset": true}',
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json().get('ok') is True
        assert 'jarvis_guided' not in client.session


def test_urgent_brake_finding_beats_the_softer_hypothesis():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'front brake lever goes to the bar'}])
    _turn("Lever goes all the way to the bar", state)
    reply = _turn("Empty or almost empty", state)
    assert 'do not ride' in reply.lower()


def test_electrical_no_power_points_at_fuse_or_battery():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'no power at all, electrical problem'}])
    _turn("No power at all", state)
    reply = _turn("Not sure", state)
    low = reply.lower()
    assert 'main fuse' in low
    assert 'battery' in low


def test_greeting_detection_does_not_swallow_symptom_words():
    from apps.core.guided_diagnostic import is_guided_intent

    assert not is_guided_intent('hello')
    # "hissing" contains "hi" but is a symptom, not a greeting.
    assert is_guided_intent('my engine is making a hissing noise')
    # A greeting followed by a real complaint must still start the flow.
    assert is_guided_intent('hello, my brakes are soft')


def test_clicking_noise_does_not_misread_a_honda_click():
    state = start_state()
    reply = _turn("Honda Wave 125, there is a clicking sound", state)
    low = reply.lower()
    assert 'wave' in low
    # "clicking" must not be mistaken for the Honda Click model.
    assert 'click 125i' not in low


def test_question_mid_flow_uses_the_full_knowledge_engine():
    from apps.core.guided_diagnostic import is_guided_intent

    assert not is_guided_intent('how do i bleed the brakes?', state={'stage': 'verdict'})
    assert not is_guided_intent('what causes a spongy brake?', state={'stage': 'narrow'})
    # Chip answers are not questions and must stay in the guided flow.
    assert is_guided_intent('Still not fixed', state={'stage': 'verdict'})


def test_general_maintenance_questions_bypass_the_guided_intake():
    from apps.core.guided_diagnostic import is_general_motorcycle_query, is_guided_intent

    questions = [
        'how many km does my motorcycle need to change oil',
        'what should I do if I want to change oil',
        'what should I check before changing my tire',
        'how do i bleed the brakes?',
        'how to check for oil leaks',
        'how do i check if my battery is dead',
        'how to check for a punctured tire',
        'oil capacity for Honda Click 125i',
        'spark plug gap for Honda Click 125i',
    ]
    for question in questions:
        assert is_general_motorcycle_query(question), question
        assert not is_guided_intent(question), question

    # Actual fault reports must keep using the guided diagnostic flow.
    assert not is_general_motorcycle_query("my engine won't start")
    assert is_guided_intent("my engine won't start")
    assert not is_general_motorcycle_query('my brakes are soft')
    assert is_guided_intent('my brakes are soft')


def test_part_location_questions_are_general_not_diagnostic():
    from apps.core.guided_diagnostic import is_general_motorcycle_query, is_guided_intent

    questions = [
        'where to locate that part',
        'where is the ECU located',
        'where is the CDI located',
        'where is the horn located',
        'where is the starter relay',
        'where is the oil filter located',
        'where can i find the battery',
        'where is the main fuse',
        'saan matatagpuan ang battery',
    ]
    for question in questions:
        assert is_general_motorcycle_query(question), question
        assert not is_guided_intent(question, state={'stage': 'area'}), question

    # Pronoun follow-ups can use a part named in the recent conversation.
    history = [{'role': 'user', 'text': 'what is an oil filter?'}]
    assert is_general_motorcycle_query('where is it located', history=history)
    assert is_general_motorcycle_query('where can i find it', history=history)
    assert not is_general_motorcycle_query('where is it located')
    assert not is_general_motorcycle_query(
        'where is it located',
        history=[{'role': 'user', 'text': "my engine won't start"}],
    )

    # "Where is the symptom coming from?" is still a diagnostic question.
    assert not is_general_motorcycle_query('where is the noise coming from')
    assert not is_general_motorcycle_query('where is the oil coming from')
    assert not is_general_motorcycle_query('where is the coolant leaking from')
    assert not is_general_motorcycle_query('where is the brake noise')
    assert not is_general_motorcycle_query('where is the oil leak')
    assert not is_general_motorcycle_query('where is the nearest mechanic')


def test_maintenance_chips_leave_the_guided_flow_for_a_direct_answer():
    from apps.core.guided_diagnostic import is_guided_intent

    assert not is_guided_intent('Oil change / maintenance', state={'stage': 'area'})
    assert not is_guided_intent('Engine oil and filter change', state={'stage': 'narrow'})
    assert not is_guided_intent('Chain clean and lubricate', state={'stage': 'area'})
    # A genuine guided option must still continue the narrowing flow.
    assert is_guided_intent('When the engine is cold', state={'stage': 'narrow'})


def test_new_symptom_after_a_verdict_restarts_narrowing():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'brakes are soft'}])
    _turn("spongy", state)
    _turn("above min", state)
    assert state['stage'] == 'verdict'

    reply = _turn("now the engine is overheating", state)
    assert state['area'] == 'overheat'
    assert state['stage'] == 'narrow'
    assert 'where to look first' in reply.lower()


def _client():
    from django.test import Client
    return Client()


def test_guided_step_by_step_procedure_walkthrough():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'brakes are soft'}])
    _turn("spongy", state)
    _turn("above min", state)
    assert state['stage'] == 'verdict'

    # User says "proceed" to commence step-by-step procedure
    reply1 = _turn("proceed", state)
    assert state['stage'] == 'procedure'
    assert 'Step 1:' in reply1
    assert 'bleed' in reply1.lower() or 'fluid' in reply1.lower()

    # User advances to next step
    reply2 = _turn("next", state)
    assert state['stage'] == 'procedure'
    assert 'Step 2:' in reply2

    # User confirms the fix worked
    reply3 = _turn("it worked", state)
    assert state['stage'] == 'done'
    assert 'back in service' in reply3.lower()


@pytest.mark.django_db
def test_orchestrate_diagnostic_procedure_commence():
    from apps.core.diagnostic_engine import orchestrate_diagnostic_response
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username='testdiaguser', password='password123')

    history = [
        {'role': 'user', 'text': 'My 2022 Honda Click 125i clicking sound when starting'},
        {'role': 'assistant', 'text': 'I am here to help you inspect and troubleshoot your vehicle step-by-step. Would you like to commence the step-by-step procedure? - [ ] 1. Check battery terminals.'},
    ]

    # User agrees to commence
    reply = orchestrate_diagnostic_response("proceed", user, history=history)
    assert reply is not None
    # Must NOT ask the user "what symptom would you like assistance with"
    assert "What specific symptom, mechanical issue, or maintenance procedure" not in reply
    # Must deliver Step 1
    assert "Step 1" in reply or "battery" in reply.lower()


@pytest.mark.django_db
def test_orchestrate_diagnostic_unsuccessful_attempt_persists_symptom():
    from apps.core.diagnostic_engine import orchestrate_diagnostic_response
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username='testdiaguser2', password='password123')

    history = [
        {'role': 'user', 'text': 'My 2022 Honda Click 125i clicking sound when starting'},
        {'role': 'assistant', 'text': 'Inspect the battery terminals for looseness or sulfate corrosion.'},
    ]

    # User reports it did not work
    reply = orchestrate_diagnostic_response("still not working", user, history=history)
    assert reply is not None
    # Must NOT ask the user what symptom they have
    assert "What specific symptom, mechanical issue, or maintenance procedure" not in reply



def test_procedure_teaches_location_when_user_does_not_know():
    """If user doesn't know where the component is located, Jarvis teaches them step-by-step."""
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'engine will not start'}])
    _turn("Rapid clicking / relay chatter", state)
    _turn("Havent checked yet", state)
    assert state['stage'] == 'verdict'

    # Start procedure
    reply_start = _turn("begin procedure", state)
    assert state['stage'] == 'procedure'
    assert "Step 1:" in reply_start

    # User says they don't know where it is located
    loc_reply = _turn("i don't know where it is located", state)
    # Jarvis must teach step by step where to find it
    assert "How to Find" in loc_reply or "📍" in loc_reply or "step-by-step" in loc_reply.lower()
    assert any(term in loc_reply.lower() for term in ['seat', 'terminal', 'battery', 'panel'])
    assert "1." in loc_reply

    # User says "found it, can we continue in that session"
    cont_reply = _turn("can we continue in that session", state)
    assert state['stage'] == 'procedure'
    assert "Step 1" in cont_reply
    assert "pick up right where we left off" in cont_reply.lower() or "continue" in cont_reply.lower()


def test_user_asks_to_continue_session_resumes_active_problem():
    """If user asks to continue the session, Jarvis maintains focus on the active problem."""
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'brakes are soft'}])
    _turn("spongy", state)
    _turn("above min", state)
    assert state['stage'] == 'verdict'

    # Commence procedure
    _turn("proceed", state)
    assert state['stage'] == 'procedure'
    assert state['procedure_index'] == 0

    # Advance to step 2
    _turn("next", state)
    assert state['procedure_index'] == 1

    # User asks "where is it"
    loc_reply = _turn("where is it located?", state)
    assert "How to Find" in loc_reply or "location" in loc_reply.lower() or "step-by-step" in loc_reply.lower()

    # User asks "can we continue in that session"
    resume_reply = _turn("can we continue in that session", state)
    assert state['stage'] == 'procedure'
    assert state['procedure_index'] == 1
    assert "Step 2" in resume_reply



def test_procedure_teaches_beginner_how_to_do_step_step_by_step():
    """When a beginner user asks how to do the step, Jarvis provides a step-by-step tutorial."""
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': 'engine will not start'}])
    _turn("Rapid clicking / relay chatter", state)
    _turn("Havent checked yet", state)
    assert state['stage'] == 'verdict'

    # Begin procedure
    _turn("begin procedure", state)
    assert state['stage'] == 'procedure'
    assert state['procedure_index'] == 0

    # User is a beginner and asks how to do this
    reply_how = _turn("i am a beginner, how do i do this?", state)
    assert state['stage'] == 'procedure'
    assert "How to Test" in reply_how or "Beginner" in reply_how or "Tools Needed" in reply_how
    assert "Tools" in reply_how
    assert "1." in reply_how
    assert "Good" in reply_how or "Normal" in reply_how or "Bad" in reply_how

    # User asks "how can we fix it?"
    reply_fix = _turn("how can we fix it?", state)
    assert state['stage'] == 'procedure'
    assert "1." in reply_fix

    # User asks again just to be sure
    reply_sure = _turn("just to be sure, are you sure?", state)
    assert state['stage'] == 'procedure'
    assert "Rest assured" in reply_sure or "safest" in reply_sure.lower() or "Step 1" in reply_sure

    # User says "can we continue in that session"
    reply_continue = _turn("can we continue in that session", state)
    assert state['stage'] == 'procedure'
    assert "Step 1" in reply_continue
    assert "continue on what we are trying to fix" in reply_continue.lower() or "pick up right where we left off" in reply_continue.lower()
