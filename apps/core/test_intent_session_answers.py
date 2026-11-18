"""Regression coverage for short status answers inside an active diagnostic session.

A reply such as "it is fully engage and yes it stay running once its warm up"
is an answer to J.A.R.V.I.S.'s previous question.  It must not be classified
as off-topic, which would reset the conversation to the generic motorcycle
intro message.
"""
from apps.core.services.intent import classify_intent, is_motorcycle_related

HISTORY = [
    {'role': 'user', 'text': 'My Yamaha Sniper 150 stalls at idle.'},
    {'role': 'assistant', 'text': 'Is it fuel-injected (FI) or carbureted, and does it stall only when cold or also when warm?'},
    {'role': 'user', 'text': 'its an carb and it happend on when its cold start'},
    {'role': 'assistant', 'text': 'Check if the manual choke lever is fully engaged during cold starts and if the engine stays running once it warms up.'},
]

STATUS_ANSWERS = [
    'it is fully engage and yes it stay running once its warm up',
    'it is fully engaged and yes it stays running once it warms up',
    'yes it stays running once warm',
    'choke is engaged and it runs fine when warm',
    'only stalls on cold start',
]


def test_guided_status_answers_stay_in_session():
    for message in STATUS_ANSWERS:
        result = classify_intent(message, history=HISTORY)
        assert result == 'diagnostic', (
            f'{message!r} was classified as {result} ({result.sub_intent})'
        )
        assert not result.is_off_topic


def test_guided_status_answers_are_motorcycle_related():
    for message in STATUS_ANSWERS:
        assert is_motorcycle_related(message.lower(), history=HISTORY), message


def test_status_words_alone_do_not_rescue_off_topic_messages():
    """The status vocabulary only applies when a session/vehicle is active."""
    assert classify_intent('the weather is warm and i stayed home') == 'off_topic'
    assert not is_motorcycle_related('the weather is warm and i stayed home')


def test_explicit_off_topic_domain_still_blocked_with_history():
    result = classify_intent('write me a poem about a warm engine', history=HISTORY)
    assert result == 'off_topic'
    assert result.sub_intent == 'creative'
