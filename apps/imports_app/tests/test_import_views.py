from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.imports_app.models import ImportBatch


@override_settings(MEDIA_ROOT='test_media')
class ImportViewsTests(TestCase):
    @patch('apps.imports_app.views.import_excel')
    def test_upload_view_creates_new_batch(self, import_excel_mock):
        import_excel_mock.return_value = {
            'total_rows': 1,
            'imported_rows': 1,
            'failed_rows': 0,
            'duplicate_rows': 0,
            'duplicate_in_file_rows': 0,
            'duplicate_previous_rows': 0,
            'inconsistencies': 0,
        }

        content = BytesIO(b'dummy excel content').getvalue()
        uploaded = SimpleUploadedFile(
            'sample.xlsx',
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post(reverse('imports_app:upload_excel'), {'file': uploaded})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImportBatch.objects.count(), 1)

    def test_history_view_renders_batches(self):
        ImportBatch.objects.create(original_filename='a.xlsx')
        response = self.client.get(reverse('imports_app:history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Historico de Importacoes')
        self.assertContains(response, 'a.xlsx')

    def test_batch_detail_view_renders_summary(self):
        batch = ImportBatch.objects.create(
            original_filename='detail.xlsx',
            total_rows=10,
            success_rows=7,
            duplicate_rows=2,
            duplicate_in_file_rows=1,
            duplicate_previous_rows=1,
            failed_rows=1,
            flagged_rows=3,
            status=ImportBatch.Status.PARTIAL,
        )

        response = self.client.get(reverse('imports_app:batch_detail', args=[batch.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detalhe do Lote')
        self.assertContains(response, 'detail.xlsx')
        self.assertContains(response, 'Duplicadas no mesmo ficheiro')
