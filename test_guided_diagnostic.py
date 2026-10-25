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
