from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import (
    DiagnosticSymptom,
    GuideRequiredPart,
    Part,
    TroubleshootingGuide,
)


class ViewerRouteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='viewer-tester', password='pass-1234')

    def test_viewer_requires_login(self):
        response = self.client.get('/motor/viewer/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/'))

    def test_viewer_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get('/motor/viewer/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mv-canvas')
        self.assertContains(response, 'motor/models/motorcycle.glb')
        self.assertContains(response, 'three@0.165.0')
        self.assertContains(response, 'animejs@3.2.2')
        self.assertContains(response, 'motor/viewer.js')
        self.assertContains(response, 'data-preset="iso"')
        self.assertContains(response, 'mv-btn-intro')


class MotorAssistantDataMigrationTests(TestCase):
    def test_dump_sample_data_is_available(self):
        symptom = DiagnosticSymptom.objects.get(pk=1)
        guide = TroubleshootingGuide.objects.get(pk=1)
        part = Part.objects.get(pk=1)
        requirement = GuideRequiredPart.objects.get(pk=1)

        self.assertEqual(symptom.symptom_name, 'Smoke near engine and front sprocket')
        self.assertEqual(guide.symptom, symptom)
        self.assertEqual(part.part_name, 'Front Sprocket Oil Seal')
        self.assertEqual(requirement.guide, guide)
        self.assertEqual(requirement.part, part)
        self.assertEqual(requirement.quantity_needed, 1)

    def test_deleting_symptom_cascades_to_guide_and_required_parts(self):
        symptom = DiagnosticSymptom.objects.get(pk=1)
        symptom.delete()

        self.assertFalse(TroubleshootingGuide.objects.filter(pk=1).exists())
        self.assertFalse(GuideRequiredPart.objects.filter(pk=1).exists())
