import pytest
from apps.core.guided_diagnostic import (
    start_state,
    handle_guided_turn,
)

def _turn(msg, state, history=None):
    history = history or []
    return handle_guided_turn(msg, None, history, state, lang='english', sir='sir')

def test_user_havent_checked_yet_at_safe_checks_guides_and_does_not_assume():
    state = start_state()
    # Step 1 -> Step 2: User states starting issue
    reply1 = _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': "My engine won't start, but dash lights turn on."}])
    assert state['stage'] == 'narrow'
    assert state['q_index'] == 0
    assert '[stage: 2]' in reply1

    # User says "haven't checked yet"
    reply2 = _turn("haven't checked yet", state)
    low2 = reply2.lower()

    # MUST NOT jump to verdict or assume "No power reaching the starter" or "dead dash"
    assert state['stage'] == 'narrow'
    assert 'no power reaching the starter' not in low2
    assert 'completely dead dash' not in low2
    # Must provide safe testing guidance
    assert 'safe' in low2 or 'test' in low2
    assert '[stage: 2]' in reply2
    assert '[chips:' in reply2

def test_dash_lights_on_does_not_diagnose_dead_dash():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': "My engine won't start, but the dash lights turn on."}])
    # Answer that starter makes no sound / total silence
    reply2 = _turn("No sound", state)
    # Then for spark question, haven't checked
    reply3 = _turn("Havent checked yet", state)
    low3 = reply3.lower()

    assert state['stage'] == 'verdict'
    # Should diagnose starter button / safety interlock open, NOT dead dash / no power!
    assert 'safety interlock' in low3 or 'starter button' in low3 or 'kill switch' in low3
    assert 'completely dead dash' not in low3
    # Check that part image is provided
    assert '[part-image:' in reply3
    assert '[stage: 3]' in reply3

def test_review_findings_provides_picture_and_stage_3():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': "engine won't start"}])
    _turn("Rapid clicking / relay chatter", state)
    reply = _turn("Havent checked yet", state)

    assert state['stage'] == 'verdict'
    assert '[part-image:' in reply
    assert 'Motorcycle' in reply
    assert '[stage: 3]' in reply
    assert 'Review Findings' in reply
    assert 'Yes, show repair plan' in reply

def test_repair_plan_activates_stage_4_with_checkbox_checklist():
    state = start_state()
    _turn("2022 Honda Click 125i", state, [{'role': 'user', 'text': "engine won't start"}])
    _turn("Rapid clicking / relay chatter", state)
    _turn("Havent checked yet", state)

    # Now ask for repair plan
    reply_plan = _turn("Yes, show repair plan", state)

    assert state['stage'] == 'procedure'
    assert '[stage: 4]' in reply_plan
    assert '- [ ]' in reply_plan
    assert 'Repair Plan' in reply_plan
    assert 'Immediate Action' in reply_plan
