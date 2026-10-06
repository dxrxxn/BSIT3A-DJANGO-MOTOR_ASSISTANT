from django.test import TestCase

from .models import (
    DiagnosticSymptom,
    GuideRequiredPart,
    Part,
    TroubleshootingGuide,
)


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

