"""
Offline unit tests for the Jarvis AI assistant.

These tests exercise the deterministic logic only (language detection, vehicle
extraction, visual intent, offline knowledge cache, rule-based diagnostic
engine) — they never call the Gemini API and consume no quota.

Run with:  pytest test_jarvis_unit.py -v
"""
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core import views
from apps.core.models import JarvisKnowledge
from apps.motor.models import DiagnosticSymptom, GuideRequiredPart, Part, TroubleshootingGuide


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username='mechanic', password='secret1234', first_name='Tony'
    )


@pytest.fixture(autouse=True)
def no_gemini(monkeypatch):
    """Force the offline code path for every test in this module."""
    monkeypatch.setattr(views, '_get_gemini_client', lambda: None)
    # Never touch the live Wikipedia search from unit tests.
    monkeypatch.setattr(views, '_search_part_image', lambda q: (None, None))


@pytest.fixture
def clean_knowledge(db):
    JarvisKnowledge.objects.all().delete()
    yield
    JarvisKnowledge.objects.all().delete()


# ---------------------------------------------------------------------------
# _detect_language
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDetectLanguage:
    def test_english(self):
        assert views._detect_language("My engine won't start") == 'english'

    def test_tagalog(self):
        assert views._detect_language("Kamusta, ayaw mag-start ng motor ko") == 'tagalog'

    def test_tagalog_ayaw(self):
        assert views._detect_language("bakit umuusok ang tambutso ko") == 'tagalog'

    def test_hiligaynon(self):
        assert views._detect_language("Maayong adlaw, indi mag-andar ang makina ko") == 'hiligaynon'

    def test_history_boosts_detection(self):
        history = [{'role': 'user', 'text': 'kamusta'}, {'role': 'user', 'text': 'ayaw mag-start'}]
        assert views._detect_language("ano kaya problema", history=history) == 'tagalog'


# ---------------------------------------------------------------------------
# _extract_vehicle_info
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExtractVehicleInfo:
    def test_full_scooter_statement(self):
        info = views._extract_vehicle_info("my 2022 Honda Click 125i won't start")
        assert info['make'] == 'Honda'
        assert info['model'] == 'Click 125i'
        assert info['year'] == '2022'
        assert info['type'] == 'scooter'

    def test_fuel_injected_keyword(self):
        info = views._extract_vehicle_info("my yamaha nmax 155 fi won't accelerate")
        assert info['make'] == 'Yamaha'
        assert info['engine_fuel'] == 'FI'

    def test_carburetor_keyword(self):
        info = views._extract_vehicle_info("fix my carburetor, it's bogging down")
        assert info['engine_fuel'] == 'Carburetor'

    def test_fi_not_matched_inside_other_words(self):
        # "fi" as a substring must not mark the vehicle as fuel-injected.
        info = views._extract_vehicle_info("my motorcycle failed to start after the traffic")
        assert info['engine_fuel'] is None

    def test_displacement(self):
        info = views._extract_vehicle_info("honda beat 110cc overheating")
        assert info['displacement'] == '110CC'

    def test_disc_brake(self):
        info = views._extract_vehicle_info("honda click disc brake lever soft")
        assert info['brake_type'] == 'disc'

    def test_from_history(self):
        history = [{'role': 'user', 'text': 'I have a 2021 yamaha aerox 155'}]
        info = views._extract_vehicle_info("it won't start", history=history)
        assert info['make'] == 'Yamaha'
        assert info['model'] == 'Aerox 155'
        assert info['year'] == '2021'


# ---------------------------------------------------------------------------
# _has_visual_intent
# ---------------------------------------------------------------------------

class TestHasVisualIntent:
    @pytest.mark.parametrize('msg', [
        'what is a caliper',
        'what is a sprocket',
        'What does a spark plug look like?',
        'picture of brake pad',
        'show me a headlight',
        'ano ang carburetor',
    ])
    def test_visual_queries(self, msg):
        assert views._has_visual_intent(msg) is True

    @pytest.mark.parametrize('msg', [
        "my engine won't start",
        'spongy brakes',
        'show me how to bleed brakes',
        'what is causing my engine to overheat',
        'what is this sound from the top end',
        'engine overheating problem',
    ])
    def test_non_visual_queries(self, msg):
        assert views._has_visual_intent(msg) is False


# ---------------------------------------------------------------------------
# Offline knowledge cache
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOfflineKnowledge:
    def test_save_and_exact_retrieval(self, user, clean_knowledge):
        views._save_offline_knowledge('why is my engine overheating', 'Check the radiator, sir.')
        hit = views._find_offline_knowledge('why is my engine overheating', user)
        assert hit == 'Check the radiator, sir.'

    def test_chitchat_not_cached(self, user, clean_knowledge):
        views._save_offline_knowledge('thank you', 'Always a pleasure, sir.')
        assert JarvisKnowledge.objects.count() == 0
        assert views._find_offline_knowledge('thank you', user) is None

    def test_overlap_match(self, user, clean_knowledge):
        views._save_offline_knowledge('brake lever feels soft and spongy', 'Bleed the brake line, sir.')
        hit = views._find_offline_knowledge('why is my brake lever soft', user)
        assert hit == 'Bleed the brake line, sir.'

    def test_no_false_match_on_unrelated_query(self, user, clean_knowledge):
        views._save_offline_knowledge('brake lever feels soft and spongy', 'Bleed the brake line, sir.')
        hit = views._find_offline_knowledge('how to change engine oil', user)
        assert hit is None

    def test_singular_plural_tokens_match(self, user, clean_knowledge):
        # Saved with plural "brakes", queried with singular context
        views._save_offline_knowledge('why do brakes squeal when stopping', 'Pads may be glazed, sir.')
        hit = views._find_offline_knowledge('brake squeal noise cause', user)
        assert hit == 'Pads may be glazed, sir.'

        # Reverse: saved singular "plate", queried with plural "plates"
        views._save_offline_knowledge('clutch plate replacement cost', 'Expect around 800 pesos, sir.')
        hit = views._find_offline_knowledge('clutch plates replacement price estimate', user)
        assert hit == 'Expect around 800 pesos, sir.'

    def test_weak_keyword_overlap_is_rejected(self, user, clean_knowledge):
        views._save_offline_knowledge('brake pads worn out replacement', 'Install new pads, sir.')
        # Shares 2 tokens but covers only ~29% of this long query — too weak to serve
        hit = views._find_offline_knowledge(
            'brake pad question about electrical wiring harness problems', user)
        assert hit is None

    def test_search_scans_full_cache_beyond_150_entries(self, user, clean_knowledge):
        views._save_offline_knowledge(
            'radiator coolant flush interval', 'Flush the coolant every 12,000 km, sir.')
        junk = [
            JarvisKnowledge(
                user_query=f'unrelated question {i} zebra velvet orbit',
                clean_query=f'unrelated question {i} zebra velvet orbit',
                keywords='zebra velvet orbit tulip quartz',
                ai_response='junk answer',
            )
            for i in range(160)
        ]
        JarvisKnowledge.objects.bulk_create(junk)
        # Push the 160 junk rows above the target in the default -updated_at order,
        # so the old [:150] scan would have missed the target entirely.
        JarvisKnowledge.objects.filter(user_query__startswith='unrelated').update(
            updated_at=timezone.now() + timedelta(minutes=5))

        hit = views._find_offline_knowledge(
            'how often should radiator coolant be flushed', user)
        assert hit == 'Flush the coolant every 12,000 km, sir.'


# ---------------------------------------------------------------------------
# Rule-based diagnostic engine (offline fallback)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRuleBasedDiagnostic:
    def _reply(self, message, user, history=None):
        return views._jarvis_rule_based_diagnostic(message, user, history=history)

    def _chips(self, reply):
        m = None
        import re
        matches = re.findall(r'\[chips:[^\]]+\]', reply)
        return matches

    def test_greeting_english(self, user):
        r = self._reply('hello', user)
        assert 'J.A.R.V.I.S.' in r
        assert self._chips(r), 'greeting must include chips'

    def test_greeting_tagalog(self, user):
        r = self._reply('kamusta', user)
        assert 'Magandang araw' in r
        assert self._chips(r)

    def test_tagalog_no_start_gets_diagnosis_not_greeting(self, user):
        r = self._reply('hindi mag-start ang makina ko', user)
        assert 'vehicle-form' in r, 'diagnostic request must not be swallowed by greeting'
        assert self._chips(r)

    def test_start_failure_no_vehicle_shows_intake_form(self, user):
        r = self._reply("engine won't start", user)
        assert '[vehicle-form:' in r
        form = json.loads(r.split('[vehicle-form:', 1)[1].split(']', 1)[0])
        assert form['category'] == 'start'
        assert self._chips(r)

    def test_start_failure_with_vehicle_asks_starter_behaviour(self, user):
        r = self._reply("my 2022 honda click 125i won't start", user)
        assert '2022 Honda Click 125i' in r
        assert 'starter' in r.lower()

    def test_brake_no_vehicle_shows_intake_and_safety(self, user):
        r = self._reply('spongy brakes', user)
        assert '[vehicle-form:' in r
        form = json.loads(r.split('[vehicle-form:', 1)[1].split(']', 1)[0])
        assert form['category'] == 'brake'
        assert 'SAFETY WARNING' in r.upper()

    def test_brake_known_vehicle_gives_bleeding_checklist(self, user):
        r = self._reply('my honda click 125i has spongy brakes', user)
        assert '- [ ]' in r, 'must include interactive checklist'
        assert 'DOT 4' in r
        assert self._chips(r)

    def test_brake_grinding_warns_stop_riding(self, user):
        r = self._reply('honda beat metal grinding when braking', user)
        assert 'Stop riding immediately' in r

    def test_overheat_safety_warning(self, user):
        r = self._reply('engine overheating', user)
        upper = r.upper()
        assert 'NEVER OPEN A HOT RADIATOR CAP' in upper
        assert '[vehicle-form:' in r

    def test_overheat_known_vehicle_checklist(self, user):
        r = self._reply('yamaha nmax overheating in traffic', user)
        assert '- [ ]' in r
        assert 'NEVER OPEN A HOT RADIATOR CAP' in r.upper()

    def test_blue_smoke_checklist(self, user):
        r = self._reply('blue smoke from exhaust', user)
        assert 'compression' in r.lower() or 'piston' in r.lower()

    def test_rapid_clicking_checklist(self, user):
        r = self._reply('rapid clicking sound when starting', user)
        assert 'Solenoid' in r or 'solenoid' in r
        assert '- [ ]' in r

    def test_engine_noise_localization(self, user):
        r = self._reply('strange engine noise', user)
        assert self._chips(r)

    def test_valve_ticking_checklist(self, user):
        r = self._reply('metallic ticking from top end', user)
        assert 'Valve' in r or 'valve' in r

    def test_visual_query_returns_image_tag(self, user):
        r = self._reply('what is a caliper', user)
        assert '[part-image:' in r
        assert '[chips:' in r

    def test_visual_query_no_vehicle_form(self, user):
        r = self._reply('show me a sprocket', user)
        assert '[part-image:' in r
        assert 'vehicle-form' not in r

    def test_unknown_part_polite_fallback(self, user):
        r = self._reply('what is a gizmoflanger', user)
        assert "couldn't find a photo" in r
        assert 'vehicle-form' not in r

    def test_thanks(self, user):
        r = self._reply('thank you', user)
        assert 'pleasure' in r.lower() or 'welcome' in r.lower()

    def test_help_lists_capabilities(self, user):
        r = self._reply('help', user)
        assert 'chips' in r

    def test_gibberish_friendly_fallback(self, user):
        r = self._reply('xyzzy plugh zorkmid', user)
        assert 'not sure' in r.lower()
        assert '[vehicle-form:' not in r
        assert '[chips:' in r

    def test_generic_followup_continues_last_topic(self, user):
        history = [
            {'role': 'user', 'text': "my motorcycle won't start"},
            {'role': 'bot', 'text': 'We will inspect the battery, starter and spark [vehicle-form: {"category": "start"}]'},
        ]
        r = self._reply('what should i check first?', user, history=history)
        assert 'vehicle-form' in r
        assert '"category": "start"' in r

    def test_tagalog_followup_continues_topic(self, user):
        history = [{'role': 'user', 'text': 'sira ang preno ng motor ko'}]
        r = self._reply('ano ang susunod?', user, history=history)
        assert 'vehicle-form' in r
        assert '"category": "brake"' in r

    def test_followup_without_topic_history_falls_back(self, user):
        r = self._reply('what should i check first?', user, history=[])
        assert '[chips:' in r

    # ── Localized (Tagalog/Hiligaynon) offline branches ──

    def test_tagalog_spongy_brakes_localized(self, user):
        r = self._reply('ang honda click 125i ko ay malambot ang preno', user)
        assert 'PAALALA SA KALIGTASAN' in r
        assert 'Diagnostic confirmation for your' not in r, 'English bleed narrative must not appear'
        assert '- [ ]' in r
        assert '[chips:' in r

    def test_hiligaynon_rapid_clicking_localized(self, user):
        r = self._reply('lagatik ang starter sang guba ko nga makina', user)
        assert 'Sunod-sunod nga pagsusuri' in r
        assert 'Interactive Troubleshooting Checklist' not in r, 'English narrative must not appear'
        assert '- [ ]' in r

    def test_tagalog_smoke_localized(self, user):
        r = self._reply('may usok sa tambutso ko', user)
        assert 'Anong kulay' in r
        assert '[chips:' in r

    def test_tagalog_gibberish_fallback_localized(self, user):
        r = self._reply('hindi ko maintindihan', user)
        assert 'Pasensya na' in r
        assert '[chips:' in r

    def test_tagalog_battery_protocol_localized(self, user):
        r = self._reply('suriin ko ba ang baterya ko', user)
        assert 'baterya' in r.lower()
        assert '12.6V' in r

    def test_hiligaynon_overheat_known_localized(self, user):
        r = self._reply('yamaha nmax ko naga-overheat, ngaa? subong lang', user)
        assert 'KUSOG NGA PAHILING SA KALIGTASAN' in r
        assert '- [ ]' in r

    def test_stats_queries(self, user, db):
        # Migration 0001 seeds 1 symptom/part/guide, so create one more of each
        # and assert the counts reflect both.
        symptom = DiagnosticSymptom.objects.create(symptom_name='Horn not working', category='Electrical')
        part = Part.objects.create(part_name='Thermostat Valve', part_number='TH-01', category='Cooling', estimated_cost='15.00')
        guide = TroubleshootingGuide.objects.create(
            symptom=symptom,
            possible_cause='Faulty horn relay',
            repair_instructions='1. Check fuse.\n2. Replace relay.',
        )
        GuideRequiredPart.objects.create(guide=guide, part=part, quantity_needed=1)

        r_parts = self._reply('how many parts', user)
        assert f'**{Part.objects.count()}**' in r_parts

        r_symptoms = self._reply('how many symptoms', user)
        assert f'**{DiagnosticSymptom.objects.count()}**' in r_symptoms

        r_guides = self._reply('how many guides', user)
        assert f'**{TroubleshootingGuide.objects.count()}**' in r_guides

    def test_database_symptom_match_includes_steps_and_parts(self, user, db):
        symptom = DiagnosticSymptom.objects.create(
            symptom_name='Horn not working', category='Electrical',
            description='Horn produces no sound when pressed.',
        )
        part = Part.objects.create(part_name='Horn Relay', estimated_cost='8.00')
        guide = TroubleshootingGuide.objects.create(
            symptom=symptom,
            possible_cause='Faulty horn relay or blown fuse',
            repair_instructions='1. Check the horn fuse.\n2. Test the horn relay.',
            advice_notes='Check wiring connector for corrosion.',
        )
        GuideRequiredPart.objects.create(guide=guide, part=part, quantity_needed=1)

        r = self._reply('my horn is not working', user)
        assert 'Horn not working' in r
        assert '- [ ]' in r
        assert 'Horn Relay' in r

    def test_part_name_lookup_preferred_when_part_specific(self, user, db):
        Part.objects.create(part_name='Horn Relay', part_number='HR-1', category='Electrical', estimated_cost='8.00')
        r = self._reply('horn relay price', user)
        assert 'Horn Relay' in r
        assert '8.00' in r

    def test_single_shared_word_does_not_match_wrong_symptom(self, user, db):
        # Seeded symptom "Smoke near engine and front sprocket" must not be
        # matched by unrelated queries sharing only one significant word.
        r = self._reply('clean my front wheel', user)
        assert 'Smoke near engine' not in r
        assert 'Front Sprocket Oil Seal' not in r

    def test_parts_lookup(self, user, db):
        Part.objects.create(part_name='Spark Plug NGK', part_number='NGK-7', category='Ignition', estimated_cost='4.50')
        r = self._reply('spark plug ngk price', user)
        assert 'Spark Plug NGK' in r
        assert '4.50' in r


# ---------------------------------------------------------------------------
# _jarvis_response fallback chain (Gemini forced offline)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestJarvisResponseFallbackChain:
    def test_rule_based_used_when_gemini_offline(self, user, clean_knowledge):
        reply = views._jarvis_response("engine won't start", user)
        assert reply
        assert '[vehicle-form:' in reply

    def test_cached_knowledge_used_when_gemini_offline(self, user, clean_knowledge, monkeypatch):
        from apps.core import diagnostic_engine
        # Force the non-diagnostic fallback chain: orchestration returns nothing,
        # Gemini is offline, so the locally cached answer must be used.
        monkeypatch.setattr(diagnostic_engine, 'orchestrate_diagnostic_response', lambda *a, **k: None)
        JarvisKnowledge.objects.create(
            user_query='why is my engine overheating',
            clean_query='why engine overheating',
            keywords='engine overheating why',
            ai_response='Cached answer: check the coolant level, sir.\n\n[chips: Radiator check | Fan check]',
        )
        reply = views._jarvis_response('why is my engine overheating', user)
        assert 'Cached answer' in reply

    def test_visual_reply_keeps_part_image(self, user, clean_knowledge):
        reply = views._jarvis_response('what is a spark plug', user)
        assert '[part-image:' in reply
        assert '[chips:' in reply

    def test_diagnostic_reply_has_no_part_image(self, user, clean_knowledge):
        reply = views._jarvis_response('spongy brakes', user)
        assert '[part-image:' not in reply

    def test_reply_without_chips_gets_default_chips(self, user, clean_knowledge, monkeypatch):
        monkeypatch.setattr(
            views, '_jarvis_gemini', lambda msg, usr, history=None: 'A witty but chip-less answer, sir.'
        )
        reply = views._jarvis_response('tell me about wrenches', user)
        assert '[chips:' in reply

    def test_visual_reply_without_chips_gets_part_chips(self, user, clean_knowledge, monkeypatch):
        monkeypatch.setattr(
            views, '_jarvis_gemini', lambda msg, usr, history=None: 'A caliper clamps the rotor, sir.'
        )
        reply = views._jarvis_response('what is a caliper', user)
        assert '[chips: What is a caliper?' in reply

    def test_tagalog_reply_gets_tagalog_fallback_chips(self, user, clean_knowledge, monkeypatch):
        from apps.core import diagnostic_engine
        monkeypatch.setattr(diagnostic_engine, 'orchestrate_diagnostic_response', lambda *a, **k: None)
        monkeypatch.setattr(
            views, '_jarvis_gemini',
            lambda msg, usr, history=None: 'Suriin natin ang makina, sir.'
        )
        reply = views._jarvis_response('ayaw mag-start ng makina ko', user)
        assert '[chips: Ayaw mag-start ng makina' in reply

    def test_hiligaynon_reply_gets_hiligaynon_fallback_chips(self, user, clean_knowledge, monkeypatch):
        from apps.core import diagnostic_engine
        monkeypatch.setattr(diagnostic_engine, 'orchestrate_diagnostic_response', lambda *a, **k: None)
        monkeypatch.setattr(
            views, '_jarvis_gemini',
            lambda msg, usr, history=None: 'Usisa-on naton ang makina, sir.'
        )
        reply = views._jarvis_response('indi mag-andar ang makina ko', user)
        assert '[chips: Indi mag-andar ang makina' in reply

    def test_general_oil_question_gets_direct_answer_without_intake(self, user, clean_knowledge):
        reply = views._jarvis_response(
            'how many km does my motorcycle need to change oil', user
        )
        assert '[vehicle-form:' not in reply
        assert '2,000' in reply
        assert 'owner' in reply.lower()
        assert '[chips:' in reply

    def test_general_tire_question_gets_pre_change_checklist(self, user, clean_knowledge):
        reply = views._jarvis_response(
            'what should I check before changing my tire', user
        )
        low = reply.lower()
        assert '[vehicle-form:' not in reply
        assert 'tread' in low
        assert 'torque' in low
        assert '[chips:' in reply

    def test_general_query_skips_diagnostic_engine(self, user, clean_knowledge, monkeypatch):
        from apps.core import diagnostic_engine

        def fail(*args, **kwargs):
            raise AssertionError('diagnostic engine must not run for general maintenance')

        monkeypatch.setattr(diagnostic_engine, 'orchestrate_diagnostic_response', fail)
        reply = views._jarvis_response('what should I do if I want to change oil', user)
        assert 'oil' in reply.lower()
        assert '[vehicle-form:' not in reply

    def test_general_query_uses_general_ai_mode(self, user, clean_knowledge, monkeypatch):
        calls = {}

        def fake_gemini(msg, usr, history=None, mode='diagnostic'):
            calls['mode'] = mode
            return 'Use JASO MA2 oil, sir.\n\n[chips: Oil interval | Tire checks | Chain care]'

        monkeypatch.setattr(views, '_jarvis_gemini', fake_gemini)
        reply = views._jarvis_response('what oil should I use', user)
        assert calls['mode'] == 'general'
        assert 'JASO MA2' in reply
        assert '[vehicle-form:' not in reply

    def test_general_location_fallback_answers_named_part(self, user, clean_knowledge, monkeypatch):
        monkeypatch.setattr(views, '_jarvis_gemini', lambda *a, **k: None)
        monkeypatch.setattr(views, '_find_offline_knowledge', lambda *a, **k: None)
        reply = views._jarvis_response('where is the ECU located', user)
        low = reply.lower()
        assert 'under the seat' in low or 'side panel' in low
        assert 'which part' not in low
        assert '[vehicle-form:' not in reply

    def test_general_location_fallback_asks_which_part_when_vague(self, user, clean_knowledge, monkeypatch):
        monkeypatch.setattr(views, '_jarvis_gemini', lambda *a, **k: None)
        monkeypatch.setattr(views, '_find_offline_knowledge', lambda *a, **k: None)
        reply = views._jarvis_response('where to locate that part', user)
        assert 'which part' in reply.lower()
        assert '[vehicle-form:' not in reply

    def test_general_location_fallback_uses_history_for_pronoun(self, user, clean_knowledge, monkeypatch):
        monkeypatch.setattr(views, '_jarvis_gemini', lambda *a, **k: None)
        monkeypatch.setattr(views, '_find_offline_knowledge', lambda *a, **k: None)
        history = [{'role': 'user', 'text': 'what is an oil filter?'}]
        reply = views._jarvis_response('where is it located', user, history=history)
        assert 'oil filter' in reply.lower()
        assert '[vehicle-form:' not in reply

    @pytest.mark.parametrize('message', [
        'where to locate that part',
        'where is the ECU located',
        'where is the horn located',
    ])
    def test_part_location_query_uses_general_ai_mode(
        self, user, clean_knowledge, monkeypatch, message
    ):
        calls = {}

        def fake_gemini(msg, usr, history=None, mode='diagnostic'):
            calls['mode'] = mode
            calls['message'] = msg
            return 'Typical location: under the seat, sir.\n\n[chips: Oil filter | Battery | Fuse box]'

        def fail(*args, **kwargs):
            raise AssertionError('diagnostic engine must not run for a part-location question')

        from apps.core import diagnostic_engine
        monkeypatch.setattr(views, '_jarvis_gemini', fake_gemini)
        monkeypatch.setattr(diagnostic_engine, 'orchestrate_diagnostic_response', fail)
        reply = views._jarvis_response(message, user, guided_state={'stage': 'area'})
        assert calls['mode'] == 'general'
        assert calls['message'] == message
        assert 'under the seat' in reply.lower()
        assert '[vehicle-form:' not in reply

    def test_general_gemini_mode_uses_general_prompt(self, user, clean_knowledge, monkeypatch):
        captured = {}

        class FakeResponse:
            text = 'General answer, sir.'
            usage_metadata = None

        class FakeModels:
            def generate_content(self, model, contents, config=None):
                captured['contents'] = contents
                captured['config'] = config
                return FakeResponse()

        class FakeClient:
            models = FakeModels()

        monkeypatch.setattr(views, '_get_gemini_client', lambda: FakeClient())
        reply = views._jarvis_gemini(
            'how often should I change oil', user, mode='general'
        )
        assert reply == 'General answer, sir.'
        assert 'GENERAL motorcycle question' in captured['contents']
        assert '9-part Step-by-Step Repair Tutor' not in captured['contents']
        assert captured['config'] is not None

    def test_general_reply_strips_intake_and_part_image(self, user, clean_knowledge, monkeypatch):
        def fake_gemini(msg, usr, history=None, mode='diagnostic'):
            return (
                'Use JASO MA2 oil, sir.\n'
                '[vehicle-form: {"category": "general"}]\n'
                '[part-image: https://example.com/oil.jpg | Oil]\n'
                '[chips: Oil interval | Tire checks]'
            )

        monkeypatch.setattr(views, '_jarvis_gemini', fake_gemini)
        reply = views._jarvis_response('what oil should I use', user)
        assert '[vehicle-form:' not in reply
        assert '[part-image:' not in reply

    def test_general_oil_answer_is_localized(self, user, clean_knowledge):
        reply = views._jarvis_response('paano mag-change oil', user)
        assert '[vehicle-form:' not in reply
        assert '2,000' in reply
        assert 'langis' in reply.lower()

    @pytest.mark.parametrize('message,needle', [
        ('how to clean and lube the chain', '500 km'),
        ('brake maintenance checklist', '2 mm'),
        ('full maintenance schedule', '2,000–4,000 km'),
    ])
    def test_general_topic_fallbacks(self, user, clean_knowledge, message, needle):
        reply = views._jarvis_response(message, user)
        assert needle in reply
        assert '[vehicle-form:' not in reply
        assert '[chips:' in reply

    def test_general_form_category_retaged_from_message(self, user, clean_knowledge, monkeypatch):
        monkeypatch.setattr(
            views, '_jarvis_gemini',
            lambda msg, usr, history=None: 'Let us diagnose, sir.\n[vehicle-form: {"category": "general"}]\n[chips: A | B | C]'
        )
        reply = views._jarvis_response("my motorcycle won't start", user)
        assert '"category": "start"' in reply

    def test_specific_form_category_untouched(self, user, clean_knowledge, monkeypatch):
        monkeypatch.setattr(
            views, '_jarvis_gemini',
            lambda msg, usr, history=None: 'Let us check it, sir.\n[vehicle-form: {"category": "brake"}]\n[chips: A | B | C]'
        )
        reply = views._jarvis_response('my motorcycle won\'t start and brakes squeal', user)
        assert '"category": "brake"' in reply
