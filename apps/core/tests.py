import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomeViewTests(TestCase):
    def test_home_renders_for_authenticated_user(self):
        user = get_user_model().objects.create_user(username='admin', password='secret1234')

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_home_requires_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)

    def test_dashboard_search_returns_matching_repair_steps_and_parts(self):
        user = get_user_model().objects.create_user(username='mechanic', password='secret1234')
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'), {'q': 'front sprocket oil seal'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['query'], 'front sprocket oil seal')
        self.assertEqual(len(response.context['diagnostic_results']), 1)
        result = response.context['diagnostic_results'][0]
        self.assertEqual(result['symptom'].symptom_name, 'Smoke near engine and front sprocket')
        self.assertTrue(result['guides'][0]['repair_steps'])
        self.assertEqual(
            result['guides'][0]['required_parts'][0].part.part_name,
            'Front Sprocket Oil Seal',
        )

    def test_dashboard_search_shows_empty_results_for_unknown_issue(self):
        user = get_user_model().objects.create_user(username='mechanic', password='secret1234')
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'), {'q': 'unlisted issue'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['diagnostic_results'], [])

    def test_dashboard_shows_jarvis_console(self):
        user = get_user_model().objects.create_user(username='mechanic', password='secret1234')
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'J.A.R.V.I.S.')
        self.assertContains(response, 'jarvis-workspace')

    def test_jarvis_chat_answers_in_character(self):
        user = get_user_model().objects.create_user(
            username='mechanic',
            password='secret1234',
            first_name='Tony',
        )
        self.client.force_login(user)

        from unittest.mock import patch
        with patch('apps.core.views._get_gemini_client', return_value=None):
            response = self.client.post(
                reverse('jarvis_chat'),
                data='{"message": "hello"}',
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        reply = response.json()['reply']
        self.assertIn('At your service', reply)
        self.assertIn('Tony', reply)

    def test_jarvis_chat_guided_flow_asks_year_and_keeps_safety(self):
        user = get_user_model().objects.create_user(
            username='mechanic',
            password='secret1234',
            first_name='Tony',
        )
        self.client.force_login(user)

        from unittest.mock import patch
        with patch('apps.core.views._get_gemini_client', return_value=None):
            first = self.client.post(
                reverse('jarvis_chat'),
                data=json.dumps({'message': 'Click 125i'}),
                content_type='application/json',
            )
            second = self.client.post(
                reverse('jarvis_chat'),
                data=json.dumps({'message': '2022'}),
                content_type='application/json',
            )
            third = self.client.post(
                reverse('jarvis_chat'),
                data=json.dumps({'message': 'Brakes'}),
                content_type='application/json',
            )

        first_reply = first.json()['reply']
        self.assertIn('What year', first_reply)
        self.assertIn('[chips:', first_reply)

        second_reply = second.json()['reply']
        self.assertIn('2022 Honda Click 125i', second_reply)
        self.assertIn('What is the problem', second_reply)

        third_reply = third.json()['reply']
        self.assertIn('DO NOT RIDE OR DRIVE', third_reply)
        self.assertIn('Where to look first', third_reply)

    def test_jarvis_chat_rejects_empty_and_invalid(self):
        user = get_user_model().objects.create_user(username='mechanic', password='secret1234')
        self.client.force_login(user)

        response = self.client.post(
            reverse('jarvis_chat'),
            data='{"message": ""}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            reverse('jarvis_chat'),
            data='not json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_jarvis_chat_requires_login(self):
        response = self.client.post(
            reverse('jarvis_chat'),
            data='{"message": "hello"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_jarvis_status_returns_quota(self):
        user = get_user_model().objects.create_user(username='mechanic', password='secret1234')
        self.client.force_login(user)

        response = self.client.get(reverse('jarvis_status'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'online')
        self.assertIn('percent_left', response.json()['quota'])


class MotorAssistantIntelligentAITests(TestCase):
    """
    Automated verification for Phase 8 requirements:
    - Diagnostic question selection & conversation memory
    - Knowledge retrieval (motorcycle and car separately)
    - Six core symptoms (no-start, brakes, overheat, battery, fuel, noises)
    - Safety tripwires & stop-riding directives
    - Local database fallback when external AI fails
    - Multilingual language selection (English, Tagalog, Hiligaynon)
    """

    def setUp(self):
        from apps.motor.knowledge import seed_default_knowledge
        seed_default_knowledge()
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', password='pass-1234', first_name='Alex')

    def test_diagnostic_question_selection_and_memory(self):
        from apps.core.diagnostic_engine import DiagnosticSession

        # Turn 1: user reports engine starting issue without specifics
        s1 = DiagnosticSession('my motorcycle will not start', [])
        self.assertIsNotNone(s1.next_question)
        self.assertEqual(s1.next_question['key'], 'starter_sound')

        # Turn 2: user answers with rapid clicking
        history = [
            {'role': 'user', 'text': 'my motorcycle will not start'},
            {'role': 'bot', 'text': 'What happens exactly when you press the starter button?'}
        ]
        s2 = DiagnosticSession('it produces rapid clicking and dash lights dim. 2022 Honda Click 125i', history)
        self.assertIn('rapid_clicking', s2.answered_questions)
        # Verify it does not re-ask starter sound
        if s2.next_question:
            self.assertNotEqual(s2.next_question['key'], 'starter_sound')

    def test_motorcycle_and_car_knowledge_retrieval(self):
        from apps.motor.knowledge import retrieve_verified_knowledge

        # Motorcycle retrieval
        moto_kb = retrieve_verified_knowledge('motorcycle rapid clicking starter', vehicle_type='motorcycle')
        self.assertTrue(len(moto_kb) > 0)
        self.assertIn(moto_kb[0]['vehicle_type'], ('motorcycle', 'all'))
        self.assertTrue(all(g['source_reference'] for g in moto_kb[0]['guides']))

        # Car retrieval
        car_kb = retrieve_verified_knowledge('car radiator steam overheating', vehicle_type='car')
        self.assertTrue(len(car_kb) > 0)
        self.assertIn(car_kb[0]['vehicle_type'], ('car', 'all'))
        self.assertEqual(car_kb[0]['urgency_level'], 'critical_stop')

    def test_all_six_core_symptom_categories(self):
        from apps.motor.knowledge import retrieve_verified_knowledge

        categories_tested = {
            'no_start': 'motorcycle will not start clicking solenoid',
            'brakes': 'spongy soft brakes master cylinder',
            'overheating': 'engine overheating radiator steam',
            'charging_battery': 'battery drain charging alternator stator',
            'fuel_delivery': 'engine bogging sputter carburetor throttle',
            'engine_noises': 'engine ticking metallic knocking rod knock',
        }

        for cat_name, query in categories_tested.items():
            results = retrieve_verified_knowledge(query)
            self.assertTrue(len(results) > 0, f"Failed knowledge retrieval for category: {cat_name}")
            guides = results[0]['guides']
            self.assertTrue(len(guides) > 0, f"No verified guides for category: {cat_name}")
            self.assertTrue(guides[0]['expected_result'])
            self.assertTrue(guides[0]['repair_instructions'])

    def test_critical_safety_warnings_enforced(self):
        from apps.core.diagnostic_engine import evaluate_safety_hazards

        # Brake failure -> Critical Stop
        brake_eval = evaluate_safety_hazards('my brakes are spongy and soft')
        self.assertIsNotNone(brake_eval)
        self.assertEqual(brake_eval['urgency'], 'critical_stop')
        self.assertIn('DO NOT RIDE OR DRIVE', brake_eval['alert_text'])

        # Overheating -> Scald Warning
        overheat_eval = evaluate_safety_hazards('radiator is overheating and boiling')
        self.assertIsNotNone(overheat_eval)
        self.assertEqual(overheat_eval['urgency'], 'critical_stop')
        self.assertIn('NEVER OPEN A HOT RADIATOR CAP', overheat_eval['alert_text'])

        # Fuel leak -> Fire Hazard
        fuel_eval = evaluate_safety_hazards('there is a fuel leak dripping raw gas')
        self.assertIsNotNone(fuel_eval)
        self.assertEqual(fuel_eval['urgency'], 'critical_stop')
        self.assertIn('FIRE HAZARD', fuel_eval['alert_text'])

        # Rod knock -> Immediate Engine Shutdown
        knock_eval = evaluate_safety_hazards('heavy rod knock from bottom of engine')
        self.assertIsNotNone(knock_eval)
        self.assertEqual(knock_eval['urgency'], 'critical_stop')
        self.assertIn('SHUT DOWN ENGINE IMMEDIATELY', knock_eval['alert_text'])

    def test_local_knowledge_fallback_when_ai_fails(self):
        from unittest.mock import patch
        from apps.core.diagnostic_engine import orchestrate_diagnostic_response

        # Mock AI caller to simulate network/API outage
        with patch('apps.core.diagnostic_engine.call_configured_ai', side_effect=RuntimeError("AI API unreachable")):
            reply = orchestrate_diagnostic_response(
                'my motorcycle brakes are spongy. Fluid is full above min line. 2022 Honda Click 125i',
                self.user,
                history=[]
            )

        self.assertIsNotNone(reply)
        # Must clearly indicate local database fallback
        self.assertIn('Verified Workshop Knowledge Base', reply)
        # Must include all 9 repair tutor components
        self.assertIn('Diagnostic summary', reply)
        self.assertIn('CRITICAL SAFETY DIRECTIVE', reply)
        self.assertIn('Probable Cause Assessment', reply)
        self.assertIn('Required Tools & Materials', reply)
        self.assertIn('Step-by-Step Diagnostic & Repair Procedures', reply)
        self.assertIn('Expected Benchmark Reading', reply)
        self.assertIn('What to do if the result differs', reply)
        self.assertIn('When to Stop & Consult a Qualified Mechanic', reply)
        self.assertIn('Did this test isolate and resolve the issue on your vehicle?', reply)

    def test_multilingual_language_selection(self):
        from apps.core.diagnostic_engine import DiagnosticSession, LocalTutorFormatter

        # English
        s_en = DiagnosticSession('my motorcycle brakes are spongy and soft. 2022 Honda Click 125i. fluid is full.', [])
        tutor_en = LocalTutorFormatter.format_tutor(s_en)
        self.assertIn('Probable Cause Assessment', tutor_en)
        self.assertIn('Required Tools & Materials', tutor_en)

        # Tagalog
        s_tl = DiagnosticSession('malambot ang preno ng motor ko. 2022 Honda Click 125i. puno naman ang fluid.', [])
        tutor_tl = LocalTutorFormatter.format_tutor(s_tl)
        self.assertIn('Pagsusuri sa Malamang na Sanhi', tutor_tl)
        self.assertIn('Mga Kailangang Gamit at Materyales', tutor_tl)

        # Hiligaynon
        s_hil = DiagnosticSession('humok ang preno sang motor ko. 2022 Honda Click 125i. puno man ang fluid.', [])
        tutor_hil = LocalTutorFormatter.format_tutor(s_hil)
        self.assertIn('Pagsusuri sa Mahimo nga Kabangdanan', tutor_hil)
        self.assertIn('Mga Kinahanglan nga Gamit kag Materyales', tutor_hil)


    def test_procedure_step_progression_in_guided_flow(self):
        user = get_user_model().objects.create_user(
            username='biker',
            password='secret1234',
            first_name='Tony',
        )
        self.client.force_login(user)

        from unittest.mock import patch
        with patch('apps.core.views._get_gemini_client', return_value=None):
            # 1. Identify bike
            r1 = self.client.post(reverse('jarvis_chat'), data=json.dumps({'message': 'Click 125i 2022'}), content_type='application/json')
            self.assertEqual(r1.status_code, 200)

            # 2. Select symptom area: Brakes
            r2 = self.client.post(reverse('jarvis_chat'), data=json.dumps({'message': 'Brakes weak or spongy'}), content_type='application/json')
            self.assertEqual(r2.status_code, 200)
            self.assertIn('Where to look first', r2.json()['reply'])

            # 3. Confirm to start Step 1
            r3 = self.client.post(reverse('jarvis_chat'), data=json.dumps({'message': 'Yes, ready to start Step 1'}), content_type='application/json')
            self.assertEqual(r3.status_code, 200)
            reply3 = r3.json()['reply']
            self.assertIn('Step 1:', reply3)

            # 4. Ask for Step 2 ("what is step 2?") - Must NOT drop out or start new session!
            r4 = self.client.post(reverse('jarvis_chat'), data=json.dumps({'message': 'what is step 2?'}), content_type='application/json')
            self.assertEqual(r4.status_code, 200)
            reply4 = r4.json()['reply']
            self.assertIn('Step 2:', reply4)
            self.assertNotIn('Ano po ang partikular na sintomas', reply4)
            self.assertNotIn('What specific symptom', reply4)

            # 5. Report step didn't work ("did not work") - Must advance to Step 3 / next check without losing symptom
            r5 = self.client.post(reverse('jarvis_chat'), data=json.dumps({'message': "didn't work"}), content_type='application/json')
            self.assertEqual(r5.status_code, 200)
            reply5 = r5.json()['reply']
            self.assertTrue('Step 3:' in reply5 or 'deeper causes' in reply5 or 'brakes' in reply5.lower())
            self.assertNotIn('What specific symptom', reply5)

    def test_holistic_session_continuity_with_unsuccessful_check(self):
        from unittest.mock import patch
        from apps.core.diagnostic_engine import orchestrate_diagnostic_response

        history = [
            {'role': 'user', 'text': 'My 2022 Honda Click 125i has soft spongy brakes.'},
            {'role': 'assistant', 'text': 'Step 1: Check master cylinder fluid level and inspect caliper for leaks.'}
        ]

        # User reports previous check was unsuccessful
        with patch('apps.core.diagnostic_engine.call_configured_ai', side_effect=RuntimeError("AI offline")):
            reply = orchestrate_diagnostic_response(
                "I checked that, it didn't work and brakes are still spongy. What is step 2?",
                self.user,
                history=history
            )

        self.assertIsNotNone(reply)
        # Must retain the brake symptom and provide step 2, not ask what symptom to fix
        self.assertNotIn('What specific symptom, mechanical issue, or maintenance procedure', reply)
        self.assertIn('Step 2', reply)


class RegistrationTests(TestCase):
    def test_register_get_renders_form(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/register.html')

    def test_register_post_creates_user_and_logs_in(self):
        data = {
            'username': 'newrider',
            'first_name': 'Juan',
            'last_name': 'Dela Cruz',
            'email': 'juan@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        }
        response = self.client.post(reverse('register'), data=data)
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(get_user_model().objects.filter(username='newrider').exists())


