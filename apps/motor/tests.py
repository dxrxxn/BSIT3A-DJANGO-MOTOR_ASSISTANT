import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.test import TestCase
from django.test import RequestFactory, override_settings

from .views import delete_model_image
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


class DeleteModelImageTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.models_dir = Path(self.temp_dir.name) / 'models'
        self.models_dir.mkdir()
        self.request_factory = RequestFactory()

    def _delete_request(self, name):
        request = self.request_factory.post('/motor/delete-image/', {'name': name})
        request.user = SimpleNamespace(is_authenticated=True)
        return request

    def test_deletes_image_from_models_directory(self):
        image_path = self.models_dir / 'uploaded.jpg'
        image_path.write_bytes(b'image')
        source_path = self.models_dir / 'src_1234abcd_uploaded.jpg'
        source_path.write_bytes(b'source')
        glb_path = self.models_dir / 'recon_1234abcd_uploaded.glb'
        glb_path.write_bytes(b'model')

        with override_settings(MEDIA_ROOT=self.temp_dir.name):
            response = delete_model_image(self._delete_request(image_path.name))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(image_path.exists())
        self.assertFalse(source_path.exists())
        self.assertFalse(glb_path.exists())
        self.assertCountEqual(
            json.loads(response.content)['deleted_names'],
            [image_path.name, source_path.name, glb_path.name],
        )

    def test_deleting_reconstruction_source_also_deletes_its_glb(self):
        source_path = self.models_dir / 'src_1234abcd_uploaded.png'
        source_path.write_bytes(b'source')
        glb_path = self.models_dir / 'recon_1234abcd_uploaded.glb'
        glb_path.write_bytes(b'model')

        with override_settings(MEDIA_ROOT=self.temp_dir.name):
            response = delete_model_image(self._delete_request(source_path.name))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(source_path.exists())
        self.assertFalse(glb_path.exists())

    def test_rejects_model_files_and_path_traversal(self):
        model_path = self.models_dir / 'engine.glb'
        model_path.write_bytes(b'model')

        with override_settings(MEDIA_ROOT=self.temp_dir.name):
            model_response = delete_model_image(self._delete_request(model_path.name))
            traversal_response = delete_model_image(self._delete_request('../outside.png'))

        self.assertEqual(model_response.status_code, 400)
        self.assertEqual(traversal_response.status_code, 400)
        self.assertTrue(model_path.exists())
