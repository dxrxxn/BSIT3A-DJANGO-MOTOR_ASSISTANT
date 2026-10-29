"""Regression tests for guide verification and the 3D viewer."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import DiagnosticSymptom, TroubleshootingGuide


class GuideVerificationTests(TestCase):
    def test_guide_verification_requires_approval_and_source(self):
        symptom = DiagnosticSymptom.objects.create(
            symptom_name='Test symptom', category='Brakes',
        )
        guide = TroubleshootingGuide.objects.create(
            symptom=symptom,
            possible_cause='Worn pads',
            repair_instructions='Inspect and replace.',
            review_status='approved',
            source_reference='Service manual section 4',
            is_verified=True,
        )
        self.assertTrue(guide.is_verified)

        guide.review_status = 'draft'
        guide.save()
        guide.refresh_from_db()
        self.assertFalse(guide.is_verified)

        guide.review_status = 'approved'
        guide.source_reference = ''
        guide.source_title = ''
        guide.is_verified = True
        guide.save()
        guide.refresh_from_db()
        self.assertFalse(guide.is_verified)


class ViewerCoverageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='viewer-coverage', password='pass-1234',
        )
        self.client.force_login(self.user)

    def test_viewer_marks_unmodelled_components_unavailable(self):
        response = self.client.get(reverse('motor:viewer'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-part="sprocket"')
        self.assertContains(response, 'data-part="battery"')
        self.assertContains(response, 'not modelled')
        self.assertContains(response, 'disabled')
        self.assertContains(response, 'mv-coverage-note')
        self.assertContains(response, 'cannot confirm wear, torque, fluid condition or part compatibility')

    def test_viewer_deep_link_contract_is_documented_in_markup(self):
        response = self.client.get(reverse('motor:viewer'), {'part': 'engine'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-part="engine"')
        self.assertContains(response, 'data-part="overview"')
