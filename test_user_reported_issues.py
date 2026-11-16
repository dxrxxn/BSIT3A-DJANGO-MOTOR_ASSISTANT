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


def test_honda_crf_recognized_directly_without_asking_which_model():
    from apps.core.views import _extract_vehicle_info
    info = _extract_vehicle_info("my motorcycle is honda crf")
    assert info['make'] == 'Honda'
    assert 'CRF' in info['model']

    state = start_state()
    reply = _turn("my motorcycle is honda crf, brakes are spongy", state)
    # Must NOT ask "Which specific Honda model do you have?" because CRF was already specified!
    assert "Which specific" not in reply
    # Must not contain Yamaha examples
    assert "MT-09" not in reply
    assert state['bike']['make'] == 'Honda'
    assert 'CRF' in state['bike']['model']


def test_brand_only_honda_uses_honda_examples_not_yamaha():
    state = start_state()
    reply1 = _turn("my motorcycle is honda", state)
    assert state['stage'] == 'bike'
    # Must include Honda examples (e.g. CRF, Click) and NOT Yamaha examples (MT-09, Aerox, Mio)
    assert 'Click' in reply1 or 'CRF' in reply1
    assert 'MT-09' not in reply1
    assert 'NMAX' not in reply1

    # User responds with "CRF 150L"
    reply2 = _turn("CRF 150L", state)
    # Must NOT reset session back to "Ano nga motor ang aayusin naton?" / restart
    assert state['stage'] in ('year', 'area')
    assert state['bike']['make'] == 'Honda'
    assert 'CRF' in state['bike']['model']


def test_all_major_motorcycle_brands_and_models_recognized():
    from apps.core.views import _extract_vehicle_info
    # Honda dual-sport
    v1 = _extract_vehicle_info("Honda CRF 300L")
    assert v1['make'] == 'Honda' and 'CRF' in v1['model']
    # Kawasaki sport
    v2 = _extract_vehicle_info("Kawasaki Ninja 400")
    assert v2['make'] == 'Kawasaki' and 'Ninja' in v2['model']
    # Suzuki underbone
    v3 = _extract_vehicle_info("Suzuki Raider 150")
    assert v3['make'] == 'Suzuki' and 'Raider' in v3['model']
    # KTM naked
    v4 = _extract_vehicle_info("KTM Duke 390")
    assert v4['make'] == 'KTM' and 'Duke' in v4['model']
    # Yamaha dual-sport
    v5 = _extract_vehicle_info("Yamaha WR 155")
    assert v5['make'] == 'Yamaha' and 'WR' in v5['model']
    # Bajaj commuter
    v6 = _extract_vehicle_info("Bajaj CT 100")
    assert v6['make'] == 'Bajaj' and 'CT' in v6['model']
    # Vespa scooter
    v7 = _extract_vehicle_info("Vespa Sprint 150")
    assert v7['make'] == 'Vespa' and 'Sprint' in v7['model']


def test_stage_bike_in_hiligaynon():
    state = start_state()
    reply1 = handle_guided_turn("ang motor ko kawasaki", None, [], state, lang='hiligaynon', sir='Glenn')
    assert state['stage'] == 'bike'
    # Should use Hiligaynon and Kawasaki examples
    assert 'Kawasaki' in reply1
    assert 'Ninja' in reply1 or 'Barako' in reply1
    # Must NOT have Yamaha MT-09 as examples
    assert 'MT-09' not in reply1

    # Next turn: Glenn answers with "Ninja 400"
    reply2 = handle_guided_turn("Ninja 400", None, [], state, lang='hiligaynon', sir='Glenn')
    # Must NOT reset to starting question
    assert state['stage'] in ('year', 'area')
    assert state['bike']['make'] == 'Kawasaki'
    assert 'Ninja' in state['bike']['model']

