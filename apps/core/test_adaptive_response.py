"""Tests for adaptive answer planning and remembered explanation styles."""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.core.models import Conversation
from apps.core.services import adaptive
from apps.core.services.assistant import respond
from apps.motor.knowledge import seed_default_knowledge


User = get_user_model()


def make_user(username='adaptive-rider'):
    return User.objects.create_user(username=username, password='secret-1234')


class TestAdaptiveDetection:
    def test_experience_and_style_normalisation(self):
        assert adaptive.normalize_experience_level('Mechanic') == 'mechanic'
        assert adaptive.normalize_experience_level('advanced') == 'mechanic'
        assert adaptive.normalize_experience_level('some experience') == 'intermediate'
        assert adaptive.normalize_experience_level('') == 'beginner'

        assert adaptive.normalize_explanation_style('step-by-step') == 'step_by_step'
        assert adaptive.normalize_explanation_style('plain language') == 'auto'
        assert adaptive.normalize_explanation_style('more details') == 'detailed'
        assert adaptive.normalize_explanation_style('bogus') == 'auto'

    @pytest.mark.parametrize('message,expected', [
        ('explain more simply', 'simple'),
        ('please give me more details', 'detailed'),
        ('walk me through it step by step', 'step_by_step'),
        ('show me the complete procedure', 'complete'),
        ('explain why this happens', 'why'),
        ('Ipaliwanag nang mas simple', 'simple'),
        ('Ipaliwanag kung bakit nangyayari ito', 'why'),
        ('Ipaliwanag kon ngaa nagakatabo ini', 'why'),
        ('my brakes are spongy', ''),
        ('why is my engine overheating?', ''),
    ])
    def test_detects_only_explicit_style_requests(self, message, expected):
        assert adaptive.detect_explanation_style_request(message) == expected

    def test_style_only_followup_does_not_swallow_a_new_symptom(self):
        assert adaptive.is_style_only_message('explain more simply')
        assert adaptive.is_style_only_message('Give me more details')
        assert adaptive.is_style_only_message('Complete procedure')
        assert not adaptive.is_style_only_message(
            'my engine is ticking, explain more simply'
        )
        assert not adaptive.is_style_only_message(
            'more details on how to bleed the brakes'
        )
        assert not adaptive.is_style_only_message(
            'what is a stator, explain more simply'
        )

    def test_style_precedence_is_detected_request_then_client_then_stored(self):
        assert adaptive.resolve_explanation_style(
            'auto', detected='why', stored='simple') == 'why'
        assert adaptive.resolve_explanation_style(
            'detailed', detected='', stored='simple') == 'detailed'
        # "auto" must not erase a style the user already chose.
        assert adaptive.resolve_explanation_style(
            'auto', detected='', stored='simple') == 'simple'


class TestAdaptivePlan:
    def test_simple_fact_gets_a_short_plan_not_a_procedure(self):
        plan = adaptive.build_response_plan(
            'where is the battery located?',
            experience_level='beginner',
        )
        assert plan.question_type == 'simple_fact'
        assert plan.effective_style == 'simple'
        assert '1-3 short sentences' in plan.length_target

    def test_symptom_gets_detailed_troubleshooting_not_forced_steps(self):
        plan = adaptive.build_response_plan(
            'my engine is ticking and losing power',
            experience_level='intermediate',
        )
        assert plan.question_type == 'troubleshooting'
        assert plan.effective_style == 'detailed'
        assert 'possible causes' in plan.structure
        assert plan.effective_style != 'step_by_step'

    def test_repair_question_gets_steps_automatically(self):
        plan = adaptive.build_response_plan(
            'how do I replace the brake pads?',
            experience_level='beginner',
        )
        assert plan.question_type == 'procedure'
        assert plan.effective_style == 'step_by_step'
        assert 'numbered steps' in plan.structure

    def test_explicit_style_overrides_question_default(self):
        plan = adaptive.build_response_plan(
            'my engine is ticking',
            experience_level='mechanic',
            style='simple',
        )
        assert plan.effective_style == 'simple'
        assert 'Direct answer' in plan.structure
        assert 'standard technical terms' in plan.terminology

    def test_safety_plan_keeps_warning_first_even_for_complete_style(self):
        plan = adaptive.build_response_plan(
            'my front brake lever feels spongy',
            safety={'severity': 'critical', 'stop_use': True},
            experience_level='mechanic',
            style='complete',
        )
        assert plan.question_type == 'safety'
        assert 'warning first' in plan.length_target.lower()

    def test_engine_safety_shape_is_recognised(self):
        plan = adaptive.build_response_plan(
            'radiator is overheating and boiling',
            safety={'urgency': 'critical_stop'},
        )
        assert plan.question_type == 'safety'

    def test_prompt_block_describes_the_selected_plan(self):
        plan = adaptive.build_response_plan(
            'where is the ECU located?',
            experience_level='mechanic',
            style='simple',
        )
        block = adaptive.adaptive_prompt_block(plan)
        assert 'ADAPTIVE RESPONSE PLAN' in block
        assert 'Rider experience: Experienced mechanic (mechanic)' in block
        assert 'Requested explanation style: Simple, plain language (simple)' in block
        assert 'Question type: simple_fact' in block
        assert 'Do not mention this plan' in block

    def test_style_chips_offer_alternatives_and_skip_current(self):
        chips = adaptive.style_chips('simple', language='english', limit=3)
        assert len(chips) == 3
        assert 'Explain more simply' not in chips
        assert 'Give me more details' in chips
        assert adaptive.style_chip_to_style('Complete procedure') == 'complete'
        assert adaptive.style_chip_to_style('Ipaliwanag sing tikang-tikang') == 'step_by_step'


@pytest.mark.django_db
def test_adaptive_plan_is_sent_to_the_structured_prompt(monkeypatch):
    from apps.core.services import assistant
    from apps.core.services.ai import AiResult

    captured = {}

    def fake_generate(prompt, **kwargs):
        captured['prompt'] = prompt
        return AiResult(
            text='Check the ignition coil and spark plug first.\n\n'
                 '[chips: It worked | Next step | Explain why this happens]',
            model='fake-model',
        )

    monkeypatch.setattr(assistant, 'is_ai_available', lambda: True)
    monkeypatch.setattr(assistant, 'generate', fake_generate)
    user = make_user('adaptive-prompt-rider')

    result = respond(
        user,
        'my engine is ticking and losing power',
        experience_level='beginner',
        explanation_style='simple',
    )

    prompt = captured['prompt']
    assert 'ADAPTIVE RESPONSE PLAN' in prompt
    assert 'Rider experience: Beginner (beginner)' in prompt
    assert 'Requested explanation style: Simple, plain language (simple)' in prompt
    assert 'Effective style for this turn: Simple, plain language (simple)' in prompt
    assert 'Question type: troubleshooting' in prompt
    assert result['structured']['experience_level'] == 'beginner'
    assert result['structured']['explanation_style'] == 'simple'


@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_style_only_followup_re_explains_without_new_symptom(client):
    seed_default_knowledge()
    user = make_user('memory-rider')
    client.force_login(user)

    first = client.post(
        reverse('jarvis_chat'),
        data=json.dumps({
            'message': 'my engine is ticking and losing power',
            'structured': True,
            'language': 'english',
            'experience_level': 'intermediate',
            'explanation_style': 'step_by_step',
        }),
        content_type='application/json',
    )
    assert first.status_code == 200
    first_data = first.json()
    conversation = Conversation.objects.get(pk=first_data['conversation_id'])
    assert conversation.experience_level == 'intermediate'
    assert conversation.explanation_style == 'step_by_step'
    symptoms_before = conversation.symptoms

    second = client.post(
        reverse('jarvis_chat'),
        data=json.dumps({
            'message': 'explain more simply',
            'structured': True,
            'conversation_id': conversation.pk,
            # An explicit "auto" from the client must not erase the style.
            'explanation_style': 'auto',
        }),
        content_type='application/json',
    )
    assert second.status_code == 200
    second_data = second.json()

    conversation.refresh_from_db()
    assert conversation.explanation_style == 'simple'
    assert conversation.experience_level == 'intermediate'
    assert conversation.symptoms == symptoms_before
    assert second_data['structured']['explanation_style'] == 'simple'


@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_assistant_remembers_requested_style_for_later_turns():
    user = make_user('persistent-style-rider')

    first = respond(user, 'how often should I change oil', explanation_style='simple')
    assert first['explanation_style'] == 'simple'

    second = respond(
        user,
        'what about the chain?',
        conversation_id=first['conversation_id'],
        explanation_style='auto',
    )
    assert second['explanation_style'] == 'simple'
    assert second['structured']['explanation_style'] == 'simple'


@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_simple_style_keeps_safety_warning_first():
    user = make_user('safety-style-rider')
    result = respond(
        user,
        'my front brake lever feels spongy and weak',
        explanation_style='simple',
    )
    reply = result['structured']['reply_text']
    assert reply.startswith('> [!CAUTION]')
    assert 'do not ride' in reply.lower() or 'do not drive' in reply.lower()


@pytest.mark.django_db
def test_legacy_diagnostic_engine_uses_adaptive_plan(monkeypatch):
    from apps.core import diagnostic_engine

    user = make_user('legacy-adaptive-rider')
    captured = {}

    def fake_call(prompt, system_instruction=None):
        captured['prompt'] = prompt
        captured['system'] = system_instruction
        return 'Check the CVT belt and rollers first.\n\n[chips: It worked | Next step]'

    monkeypatch.setattr(diagnostic_engine, 'call_configured_ai', fake_call)

    reply = diagnostic_engine.orchestrate_diagnostic_response(
        "Honda Click 125i won't accelerate properly",
        user,
        experience_level='mechanic',
        explanation_style='why',
    )

    assert 'CVT belt' in reply
    system = captured['system']
    assert 'ADAPTIVE RESPONSE PLAN' in system
    assert 'Rider experience: Experienced mechanic (mechanic)' in system
    assert 'Requested explanation style: Explain why it happens (why)' in system
    assert 'Effective style for this turn: Explain why it happens (why)' in system
    assert '9-part Step-by-Step Repair Tutor' not in system
