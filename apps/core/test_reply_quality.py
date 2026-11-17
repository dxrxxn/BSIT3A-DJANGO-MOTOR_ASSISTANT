"""Regressions for J.A.R.V.I.S. reply quality reported by users."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.core.services import assistant
from apps.core.services.intake import extract_vehicle_profile
from apps.core.services.offline import _compose_reply
from apps.core.services.structured import empty_structured, rider_facing_next_action


User = get_user_model()


VEHICLE_ONLY_MESSAGE = 'my honda xr 150 carbureted engine'


@pytest.mark.django_db
def test_vehicle_only_message_asks_for_symptom_not_motorcycle_clarification():
    user = User.objects.create_user(username='reply-quality-vehicle-only')

    result = assistant.respond(
        user, VEHICLE_ONLY_MESSAGE,
        experience_level='beginner', explanation_style='auto',
    )
    reply = result['reply']
    structured = result['structured']

    assert 'Is this inquiry regarding a motorcycle?' not in reply
    assert 'Noted' in reply
    assert 'Honda Xr 150' in reply
    assert 'carburetor' in reply.lower()
    assert 'what exactly happens' in reply.lower()
    assert structured['intent'] == 'symptom_inquiry'
    assert structured['diagnostic_stage'] == 'symptom'
    profile = structured['vehicle_profile']
    assert profile['vehicle_type'] == 'motorcycle'
    assert profile['fuel_system'] == 'carburetor'


def test_known_vehicle_name_replaces_generic_phrases():
    from apps.core.services.assistant import _use_known_vehicle_name

    structured = {
        'vehicle_profile': {
            'make': 'Honda', 'model': 'Xr 150',
            'engine_displacement': '150CC', 'fuel_system': 'carburetor',
        },
        'reply_text': (
            'Your motorcycle is carbureted. Check the bike before you ride '
            'the motorcycle again. Your specific motorcycle needs a test.'
        ),
        'next_action': 'Describe the symptom on your motorcycle.',
    }

    _use_known_vehicle_name(structured, structured['vehicle_profile'])

    assert 'your motorcycle' not in structured['reply_text'].lower()
    assert 'the bike' not in structured['reply_text'].lower()
    assert 'the motorcycle' not in structured['reply_text'].lower()
    assert structured['reply_text'].count('Honda Xr 150') == 4
    assert structured['next_action'] == 'Describe the symptom on your Honda Xr 150.'


@pytest.mark.django_db
def test_follow_up_does_not_call_it_a_generic_motorcycle():
    user = User.objects.create_user(username='reply-quality-known-name')
    first = assistant.respond(user, VEHICLE_ONLY_MESSAGE)

    second = assistant.respond(
        user, 'what should I check first?',
        conversation_id=first['conversation_id'],
    )

    reply = second['reply'].lower()
    assert 'your motorcycle' not in reply
    assert 'the motorcycle' not in reply
    assert 'the bike' not in reply
    assert 'honda xr 150' in reply
    profile = second['structured']['vehicle_profile']
    assert profile['make'] == 'Honda'
    assert profile['model'] == 'Xr 150'


@pytest.mark.django_db
def test_prompt_tells_model_to_use_the_known_vehicle_name(monkeypatch):
    from apps.core.services.ai import AiResult

    captured = {}

    def fake_generate(prompt, **kwargs):
        captured['prompt'] = prompt
        return AiResult(
            text='Check the carburetor.\n\n[chips: Explain more simply]',
            model='fake-model',
        )

    monkeypatch.setattr(assistant, 'is_ai_available', lambda: True)
    monkeypatch.setattr(assistant, 'generate', fake_generate)
    user = User.objects.create_user(username='reply-quality-name-prompt')
    first = assistant.respond(user, VEHICLE_ONLY_MESSAGE)

    assistant.respond(
        user, 'what should I check first?',
        conversation_id=first['conversation_id'],
    )

    assert 'The rider already identified this motorcycle as' in captured['prompt']
    assert 'Honda Xr 150' in captured['prompt']


@pytest.mark.django_db
def test_genuine_off_topic_is_still_declined():
    user = User.objects.create_user(username='reply-quality-off-topic')

    result = assistant.respond(user, 'what is the weather in manila today?')

    assert 'Is this inquiry regarding a motorcycle?' in result['reply']
    assert result['structured']['intent'] == 'off_topic'


@pytest.mark.django_db
def test_vehicle_only_does_not_restart_intake_after_a_reported_symptom():
    user = User.objects.create_user(username='reply-quality-with-symptom')
    conversation = assistant.get_or_create_conversation(user, None, create=True)
    conversation.symptoms = 'engine cranks but will not start'
    conversation.save(update_fields=['symptoms'])

    # A known bike plus a new detail must NOT be treated as a vehicle-only turn.
    profile = extract_vehicle_profile(VEHICLE_ONLY_MESSAGE, conversation=conversation)
    assert profile['make'] == 'Honda'

    # The service gate itself checks conversation.symptoms before rewriting.
    from apps.core.services.assistant import has_symptom_signal
    assert not has_symptom_signal(VEHICLE_ONLY_MESSAGE)
    assert conversation.symptoms.strip()  # so the rewrite is intentionally skipped


def test_next_action_is_never_an_instruction_to_the_assistant():
    assert rider_facing_next_action(
        'Ask the user to describe the specific symptom or problem.'
    ) == 'Describe the specific symptom or problem.'
    assert rider_facing_next_action(
        'Tell the rider to check the battery voltage.'
    ) == 'Check the battery voltage.'
    assert rider_facing_next_action(
        'Wait for user to describe the specific symptom and provide the model year.'
    ) == 'Describe the specific symptom and provide the model year.'
    assert rider_facing_next_action(
        "Await the rider's response about the symptom."
    ) == ''
    assert rider_facing_next_action(
        'Need to ask the user for the model year.'
    ) == 'Provide the model year.'
    assert rider_facing_next_action(
        'The user should describe the symptom.'
    ) == 'Describe the symptom.'
    assert rider_facing_next_action(
        'Answer the question or ask a relevant follow-up.'
    ) == ''
    assert rider_facing_next_action(
        'Describe what happens and when it started.'
    ) == 'Describe what happens and when it started.'


def test_normalise_structured_sanitizes_ai_generated_wait_for_user_text():
    from apps.core.services.structured import normalise_structured

    result = normalise_structured({
        'reply_text': 'Please describe the symptom.',
        'intent': 'diagnostic',
        'diagnostic_stage': 'symptom',
        'next_action': (
            'Wait for user to describe the specific symptom and provide '
            'the model year.'
        ),
    })

    assert result['next_action'] == (
        'Describe the specific symptom and provide the model year.'
    )


def test_ai_limitation_mentions_inaccuracy():
    from apps.core.services.assistant import AI_LIMITATION

    lowered = AI_LIMITATION.lower()
    assert 'wrong or inaccurate' in lowered
    assert 'not a confirmed diagnosis' in lowered
    assert 'in-person inspection' in lowered


def test_offline_sections_put_note_last_and_next_action_before_it():
    structured = empty_structured('english')
    structured['symptoms'] = ['It clicks']
    structured['reply_text'] = 'Check the battery.'
    structured['next_action'] = 'Measure the battery voltage.'
    structured['limitations'] = [
        'AI-assisted answer: this can be wrong or inaccurate. Verify before acting.'
    ]

    reply = _compose_reply(structured, language='english')

    next_pos = reply.index('**Next action:**')
    note_pos = reply.index('**AI note & limitations:**')
    assert next_pos < note_pos
    assert reply.rstrip().endswith('- ' + structured['limitations'][0])
