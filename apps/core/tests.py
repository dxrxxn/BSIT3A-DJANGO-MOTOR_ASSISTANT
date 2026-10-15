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
