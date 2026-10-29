"""Regression tests for the structured assistant, safety and photos."""
from __future__ import annotations

import io
import json
import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.core.models import ChatTurn, Conversation, ImageUpload
from apps.core.services.safety import assess_safety
from apps.core.services.structured import normalise_structured
from apps.motor.knowledge import seed_default_knowledge


User = get_user_model()


def make_user(username='rider'):
    return User.objects.create_user(username=username, password='secret-1234')


def jpeg_upload(name='photo.jpg', size=(320, 240)):
    PIL = pytest.importorskip('PIL.Image')
    buffer = io.BytesIO()
    PIL.new('RGB', size, (120, 30, 30)).save(buffer, format='JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


@pytest.fixture
def private_media(tmp_path, monkeypatch):
    """Point the private image field at a temporary directory."""
    field = ImageUpload._meta.get_field('file')
    storage = field.storage
    monkeypatch.setattr(storage, '_location', str(tmp_path), raising=False)
    storage.__dict__.pop('location', None)
    yield tmp_path
    storage.__dict__.pop('location', None)


# ---------------------------------------------------------------------------
# Safety and multilingual behaviour
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize('language,message,needle', [
    ('english', 'my front brake lever feels spongy and weak', 'Do not ride or drive'),
    ('tagalog', 'malambot ang preno ng motor ko', 'Huwag munang i-maneho'),
    ('hiligaynon', 'humok ang preno sang motor ko', 'Indi gid pagpadalagnon'),
])
def test_brake_safety_warning_is_multilingual(language, message, needle):
    result = assess_safety(message, language=language)

    assert result['severity'] == 'critical'
    assert result['stop_use'] is True
    assert result['warnings']
    assert needle in result['warnings'][0]


@pytest.mark.django_db
def test_symptom_alone_is_not_confirmed():
    result = assess_safety('my front brake lever feels spongy')

    assert result['severity'] == 'critical'
    assert result['stop_use'] is True
    # The warning is a possibility, not a diagnosis.
    assert 'may be compromised' in result['warnings'][0].lower()


@pytest.mark.django_db
def test_procedure_phrasing_does_not_suppress_a_brake_leak_warning():
    result = assess_safety('brake fluid leak, how do I bleed it?')

    assert result['severity'] == 'critical'
    assert result['stop_use'] is True
    assert 'brake_failure' in result['keys']


@pytest.mark.django_db
def test_exhaust_smoke_does_not_suppress_a_fire_report():
    result = assess_safety('the engine is on fire and there is exhaust smoke')

    assert result['severity'] == 'critical'
    assert result['stop_use'] is True
    assert 'fire_or_electrical_smoke' in result['keys']


@pytest.mark.django_db
@pytest.mark.parametrize('language,context', [
    ('english', 'my brakes failed on the highway'),
    ('tagalog', 'malambot ang preno ng motor ko'),
    ('hiligaynon', 'humok ang preno sang motor ko'),
])
def test_earlier_critical_fact_survives_a_follow_up_question(language, context):
    result = assess_safety(
        'paano ko i-bleed ang preno?' if language != 'english' else 'how do I check the fluid?',
        context=context,
        language=language,
    )

    assert result['severity'] == 'critical'
    assert result['stop_use'] is True
    assert 'brake_failure' in result['keys']


# ---------------------------------------------------------------------------
# Structured endpoint and memory
# ---------------------------------------------------------------------------

@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_structured_chat_is_safety_first_and_persists_memory(client):
    seed_default_knowledge()
    user = make_user()
    client.force_login(user)

    response = client.post(
        reverse('jarvis_chat'),
        data=json.dumps({
            'message': 'my front brake lever feels spongy and weak',
            'structured': True,
            'language': 'english',
            'experience_level': 'beginner',
        }),
        content_type='application/json',
    )

    assert response.status_code == 200
    data = response.json()
    assert data['offline'] is True
    assert data['ai_configured'] is False
    assert data['conversation_id']
    structured = data['structured']
    assert structured['safety']['severity'] == 'critical'
    assert structured['safety']['warnings']
    assert structured['reply_text'].startswith('> [!CAUTION]')
    assert structured['offline'] is True

    conversation = Conversation.objects.get(pk=data['conversation_id'])
    assert conversation.user == user
    assert conversation.turns.count() == 2
    assert conversation.turns.filter(role='assistant', structured__isnull=False).count() == 1

    # The same server-side conversation is reused; history is not trusted from
    # the browser.
    second = client.post(
        reverse('jarvis_chat'),
        data=json.dumps({
            'message': 'It started after I changed the brake fluid',
            'structured': True,
            'conversation_id': data['conversation_id'],
        }),
        content_type='application/json',
    )
    assert second.status_code == 200
    assert second.json()['conversation_id'] == data['conversation_id']
    assert conversation.turns.count() == 4
    assert Conversation.objects.filter(user=user).count() == 1


@override_settings(GEMINI_API_KEY='')
@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_offline_answer_discloses_that_a_photo_was_not_analysed():
    from apps.core.services.assistant import respond

    user = make_user('offline-photo')
    image = SimpleNamespace(pk=1, data=b'\xff\xd8', mime_type='image/jpeg')

    result = respond(user, 'my front brake feels spongy', image=image)

    assert result['offline'] is True
    limitations = ' '.join(result['structured']['limitations']).lower()
    assert 'photo was not analysed' in limitations


@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_structured_location_question_answers_without_vehicle_intake():
    from apps.core.services.assistant import respond

    user = make_user('location-rider')
    result = respond(user, 'where is the ECU located')
    structured = result['structured']

    assert result['offline'] is True
    assert structured['intent'] == 'general_motorcycle_question'
    assert structured['diagnostic_stage'] == 'general'
    assert structured['missing_questions'] == []
    assert 'under the seat' in structured['reply_text'].lower()
    assert '[chips:' in structured['reply_text']


@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_structured_vague_location_question_asks_which_part_not_vehicle():
    from apps.core.services.assistant import respond

    user = make_user('vague-location-rider')
    result = respond(user, 'where to locate that part')
    structured = result['structured']

    assert structured['intent'] == 'general_motorcycle_question'
    assert structured['missing_questions'] == []
    assert 'which part' in structured['reply_text'].lower()
    assert 'vehicle' not in structured['reply_text'].lower()


@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_structured_pronoun_location_uses_conversation_history():
    from apps.core.services.assistant import respond

    user = make_user('pronoun-location-rider')
    first = respond(user, 'where is the oil filter located')
    second = respond(
        user,
        'where is it located',
        conversation_id=first['conversation_id'],
    )
    structured = second['structured']

    assert structured['intent'] == 'general_motorcycle_question'
    assert structured['missing_questions'] == []
    assert 'oil filter' in structured['reply_text'].lower()
    assert 'which part' not in structured['reply_text'].lower()


@pytest.mark.django_db
def test_structured_general_question_uses_general_ai_prompt(monkeypatch):
    from apps.core.services import assistant
    from apps.core.services.ai import AiResult

    captured = {}

    def fake_generate(prompt, **kwargs):
        captured['prompt'] = prompt
        captured['system'] = kwargs.get('system_instruction')
        return AiResult(
            text='The ECU is usually under the seat, sir.\n\n[chips: Battery | Fuse box | Wiring]',
            model='fake-general-model',
        )

    monkeypatch.setattr(assistant, 'is_ai_available', lambda: True)
    monkeypatch.setattr(assistant, 'generate', fake_generate)
    user = make_user('general-ai-rider')
    result = assistant.respond(user, 'where is the ECU located')
    structured = result['structured']

    assert result['mode'] == 'ai'
    assert result['offline'] is False
    assert structured['intent'] == 'general_motorcycle_question'
    assert structured['missing_questions'] == []
    assert 'friendly and knowledgeable motorcycle assistant' in captured['system']
    assert 'where is the ECU located' in captured['prompt']
    assert 'under the seat' in structured['reply_text'].lower()


@override_settings(GEMINI_API_KEY='')
@pytest.mark.django_db
def test_structured_fault_and_narrative_followup_stay_diagnostic():
    from apps.core.services.assistant import respond

    user = make_user('diagnostic-rider')
    fault = respond(user, 'my front brake feels spongy')
    assert fault['structured']['intent'] != 'general_motorcycle_question'
    assert fault['structured']['diagnostic_stage'] != 'general'

    follow_up = respond(user, 'It started after I changed the brake fluid')
    assert follow_up['structured']['intent'] != 'general_motorcycle_question'
    assert follow_up['structured']['diagnostic_stage'] != 'general'


@pytest.mark.django_db
def test_structured_chat_rejects_another_users_conversation(client):
    owner = make_user('owner')
    other = make_user('other')
    conversation = Conversation.objects.create(user=owner, title='Owner session')

    client.force_login(other)
    response = client.post(
        reverse('jarvis_chat'),
        data=json.dumps({
            'message': 'my brakes feel weak',
            'structured': True,
            'conversation_id': conversation.pk,
        }),
        content_type='application/json',
    )

    assert response.status_code == 200
    data = response.json()
    assert data['conversation_id'] != conversation.pk
    assert Conversation.objects.get(pk=data['conversation_id']).user == other
    assert conversation.turns.count() == 0


# ---------------------------------------------------------------------------
# Rate limits and privacy
# ---------------------------------------------------------------------------

@override_settings(GEMINI_API_KEY='', CHAT_RATE_LIMIT_PER_MINUTE=1)
@pytest.mark.django_db
def test_chat_rate_limit_returns_429(client):
    cache.clear()
    user = make_user()
    client.force_login(user)
    payload = json.dumps({'message': 'hello', 'structured': True})

    first = client.post(reverse('jarvis_chat'), data=payload, content_type='application/json')
    second = client.post(reverse('jarvis_chat'), data=payload, content_type='application/json')

    assert first.status_code == 200
    assert second.status_code == 429
    assert second['Retry-After']
    assert 'Too many chat requests' in second.json()['error']
    cache.clear()


@pytest.mark.django_db
def test_image_upload_is_private_reencoded_and_owner_only(client, private_media):
    user = make_user('photo-owner')
    client.force_login(user)

    response = client.post(
        reverse('jarvis_image_upload'),
        data={'image': jpeg_upload('diagnostic.png', size=(2200, 1200))},
    )
    assert response.status_code == 200
    data = response.json()
    image = ImageUpload.objects.get(pk=data['image_id'])
    assert image.user == user
    assert image.mime_type == 'image/jpeg'
    assert image.width <= 1800 and image.height <= 1800
    assert image.original_name.endswith('.jpg')
    assert str(private_media) in image.file.path
    assert '/jarvis/image/' in data['url']

    served = client.get(data['url'])
    assert served.status_code == 200
    assert served['Content-Type'] == 'image/jpeg'
    assert served['Cache-Control'].startswith('private')

    other = make_user('photo-other')
    client.force_login(other)
    denied = client.get(data['url'])
    assert denied.status_code == 404


@pytest.mark.django_db
def test_image_upload_rejects_non_image_without_leaking_details(client, private_media):
    user = make_user()
    client.force_login(user)
    bad = SimpleUploadedFile('not-a-photo.txt', b'this is not an image', content_type='text/plain')

    response = client.post(reverse('jarvis_image_upload'), data={'image': bad})

    assert response.status_code == 400
    body = response.json()['error'].lower()
    assert 'jpeg' in body or 'readable' in body
    assert 'traceback' not in body
    assert ImageUpload.objects.count() == 0


# ---------------------------------------------------------------------------
# Sources and unpublished knowledge
# ---------------------------------------------------------------------------

def test_known_vehicle_profile_wins_over_model_guess():
    from apps.core.services.assistant import _merge_profile

    structured = _merge_profile(
        {
            'vehicle_profile': {
                'make': 'Kawasaki',
                'model': 'Ninja 400',
                'year': '2024',
            },
        },
        {
            'make': 'Honda',
            'model': 'Click 125i',
            'year': '',
        },
    )

    assert structured['vehicle_profile']['make'] == 'Honda'
    assert structured['vehicle_profile']['model'] == 'Click 125i'
    assert structured['vehicle_profile']['year'] == '2024'


def test_model_part_numbers_and_compatibility_are_not_trusted():
    structured = normalise_structured({
        'reply_text': 'Inspect the front pads.',
        'required_parts': [
            {
                'name': 'Front brake pads',
                'part_number': 'FAKE-999',
                'compatibility_verified': True,
            },
        ],
    })

    part = structured['required_parts'][0]
    assert part['part_number'] == ''
    assert part['compatibility_verified'] is False


def test_local_part_record_is_the_only_source_of_part_numbers():
    allowed = {
        'front brake pads': {
            'name': 'Front brake pads',
            'part_number': 'BP-100',
            'compatibility_verified': True,
        },
    }
    structured = normalise_structured(
        {
            'reply_text': 'Inspect the front pads.',
            'required_parts': [
                {
                    'name': 'Front Brake Pads',
                    'part_number': 'FAKE-999',
                    'compatibility_verified': True,
                },
            ],
        },
        allowed_parts=allowed,
    )

    part = structured['required_parts'][0]
    assert part['part_number'] == 'BP-100'
    assert part['compatibility_verified'] is True


def test_unverified_local_part_stays_unverified():
    allowed = {
        'front brake pads': {
            'name': 'Front brake pads',
            'part_number': 'BP-100',
            'compatibility_verified': False,
        },
    }
    structured = normalise_structured(
        {
            'reply_text': 'Inspect the front pads.',
            'required_parts': [
                {
                    'name': 'Front brake pads',
                    'part_number': 'BP-100',
                    'compatibility_verified': True,
                },
            ],
        },
        allowed_parts=allowed,
    )

    part = structured['required_parts'][0]
    assert part['part_number'] == 'BP-100'
    assert part['compatibility_verified'] is False


def test_model_sources_not_in_local_evidence_are_dropped():
    structured = normalise_structured(
        {
            'reply_text': 'Possible cause needs testing.',
            'sources': [
                {'title': 'Invented manual', 'reference': 'Page 999'},
            ],
        },
        language='english',
        evidence_sources=[{'title': 'Local reviewed record', 'reference': 'Record 1'}],
    )

    assert structured['sources'] == [
        {'title': 'Local reviewed record', 'reference': 'Record 1', 'reviewed': True, 'date': ''},
    ]


@pytest.mark.django_db
def test_unapproved_or_unsourced_guides_are_not_retrieved():
    from apps.motor.models import DiagnosticSymptom, TroubleshootingGuide

    symptom = DiagnosticSymptom.objects.create(
        symptom_name='Test front brake symptom',
        category='Brakes',
        description='front brake test',
        system='Brakes',
        vehicle_type='motorcycle',
    )
    # Approved but no source: the model guard forces is_verified off.
    unsourced = TroubleshootingGuide.objects.create(
        symptom=symptom,
        possible_cause='Unsourced brake cause',
        repair_instructions='Do a test.',
        review_status='approved',
        source_reference='',
        is_verified=True,
        system='Brakes',
        vehicle_type='motorcycle',
    )
    unsourced.refresh_from_db()
    assert unsourced.is_verified is False

    # A source alone is not enough without an approved review.
    pending = TroubleshootingGuide.objects.create(
        symptom=symptom,
        possible_cause='Pending brake cause',
        repair_instructions='Do a test.',
        review_status='pending',
        source_reference='Real manual, checked',
        is_verified=True,
        system='Brakes',
        vehicle_type='motorcycle',
    )
    pending.refresh_from_db()
    assert pending.is_verified is False

    from apps.motor.knowledge import retrieve_verified_knowledge
    assert retrieve_verified_knowledge('test front brake symptom', vehicle_type='motorcycle') == []


# ---------------------------------------------------------------------------
# Legacy AI paths must use environment-driven models and safe logging
# ---------------------------------------------------------------------------

class _FakeModels:
    def __init__(self, failures=0):
        self.calls = []
        self.failures = failures

    def generate_content(self, *, model, contents):
        self.calls.append(model)
        if self.failures:
            self.failures -= 1
            raise RuntimeError('raw-provider-detail-must-not-be-logged')
        return SimpleNamespace(text='Grounded local answer.', usage_metadata=None)


@override_settings(
    GEMINI_MODEL='configured-model',
    GEMINI_FALLBACK_MODEL='configured-fallback',
)
@pytest.mark.django_db
def test_legacy_gemini_uses_env_model_and_fallback(caplog):
    from apps.core import views as core_views

    models = _FakeModels(failures=1)
    client = SimpleNamespace(models=models)
    user = make_user('legacy-ai')

    with caplog.at_level(logging.INFO):
        with patch.object(core_views, '_get_gemini_client', return_value=client):
            reply = core_views._jarvis_gemini('brake noise', user)

    assert reply == 'Grounded local answer.'
    assert models.calls == ['configured-model', 'configured-fallback']
    assert 'raw-provider-detail' not in caplog.text


@override_settings(
    AI_PROVIDER='gemini',
    GEMINI_MODEL='primary-model',
    GEMINI_FALLBACK_MODEL='fallback-model',
)
@pytest.mark.django_db
def test_diagnostic_engine_uses_configured_fallback_without_raw_logs(caplog):
    from apps.core import diagnostic_engine

    models = _FakeModels(failures=1)
    client = SimpleNamespace(models=models)

    with caplog.at_level(logging.INFO):
        with patch('apps.core.views._get_gemini_client', return_value=client):
            reply = diagnostic_engine.call_configured_ai('diagnostic prompt')

    assert reply == 'Grounded local answer.'
    assert models.calls == ['primary-model', 'fallback-model']
    assert 'raw-provider-detail' not in caplog.text
