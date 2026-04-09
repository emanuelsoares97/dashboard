from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.imports_app.models import ImportBatch
from apps.imports_app.views import import_batch_detail
from apps.imports_app.views import import_excel
from apps.imports_app.views import import_history
from apps.imports_app.views import upload_excel


@override_settings(MEDIA_ROOT='test_media')
class ImportViewsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='imports-supervisor', password='testpass123')
        supervisors_group, _ = Group.objects.get_or_create(name='Supervisores')
        user.groups.add(supervisors_group)
        self.client.force_login(user)

    def test_views_facade_exports_expected_symbols(self):
        self.assertTrue(callable(upload_excel))
        self.assertTrue(callable(import_history))
        self.assertTrue(callable(import_batch_detail))
        self.assertTrue(callable(import_excel))

    def test_upload_view_get_renders_form_and_recent_batches(self):
        ImportBatch.objects.create(original_filename='recent.xlsx')

        response = self.client.get(reverse('imports_app:upload_excel'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('recent_batches', response.context)
        self.assertTemplateUsed(response, 'imports_app/upload.html')

    @patch('apps.imports_app.views.import_excel')
    def test_upload_view_creates_new_batch(self, import_excel_mock):
        import_excel_mock.return_value = {
            'total_rows': 1,
            'imported_rows': 1,
            'skipped_non_retention_rows': 0,
            'consolidated_existing_rows': 0,
            'failed_rows': 0,
            'duplicate_rows': 0,
            'duplicate_in_file_rows': 0,
            'duplicate_previous_rows': 0,
            'inconsistencies': 0,
        }

        content = BytesIO(b'dummy csv content').getvalue()
        uploaded = SimpleUploadedFile(
            'sample.csv',
            content,
            content_type='text/csv',
        )

        response = self.client.post(reverse('imports_app:upload_excel'), {'file': uploaded})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImportBatch.objects.count(), 1)

    @patch('apps.imports_app.views.import_excel')
    def test_upload_view_sets_failed_status_when_import_raises(self, import_excel_mock):
        import_excel_mock.side_effect = RuntimeError('Erro de teste na importacao')

        content = BytesIO(b'dummy csv content').getvalue()
        uploaded = SimpleUploadedFile(
            'sample_error.csv',
            content,
            content_type='text/csv',
        )

        response = self.client.post(reverse('imports_app:upload_excel'), {'file': uploaded})
        self.assertEqual(response.status_code, 302)

        batch = ImportBatch.objects.get(original_filename='sample_error.csv')
        self.assertEqual(batch.status, ImportBatch.Status.FAILED)
        self.assertIn('Erro de teste na importacao', batch.error_log)

    @patch('apps.imports_app.views.import_excel')
    def test_upload_view_handles_empty_import_result(self, import_excel_mock):
        import_excel_mock.return_value = {
            'total_rows': 0,
            'imported_rows': 0,
            'skipped_non_retention_rows': 0,
            'consolidated_existing_rows': 0,
            'failed_rows': 0,
            'duplicate_rows': 0,
            'duplicate_in_file_rows': 0,
            'duplicate_previous_rows': 0,
            'inconsistencies': 0,
        }

        content = BytesIO(b'dummy csv content').getvalue()
        uploaded = SimpleUploadedFile(
            'sample_empty.csv',
            content,
            content_type='text/csv',
        )

        response = self.client.post(reverse('imports_app:upload_excel'), {'file': uploaded})
        self.assertEqual(response.status_code, 302)

        batch = ImportBatch.objects.get(original_filename='sample_empty.csv')
        self.assertEqual(batch.status, ImportBatch.Status.PENDING)

    def test_history_view_renders_batches(self):
        ImportBatch.objects.create(original_filename='a.xlsx')
        response = self.client.get(reverse('imports_app:history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Histórico de Importações')
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

    def test_batch_detail_view_redirects_when_batch_does_not_exist(self):
        response = self.client.get(reverse('imports_app:batch_detail', args=[999999]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('imports_app:history'))

    def test_assistant_cannot_access_import_pages(self):
        self.client.logout()
        user = get_user_model().objects.create_user(username='imports-assistant', password='testpass123')
        assistants_group, _ = Group.objects.get_or_create(name='Assistentes')
        user.groups.add(assistants_group)
        self.client.force_login(user)

        response = self.client.get(reverse('imports_app:upload_excel'))

        self.assertEqual(response.status_code, 403)

    def test_superuser_can_access_import_pages(self):
        self.client.logout()
        user = get_user_model().objects.create_superuser(
            username='imports-root',
            email='imports-root@example.com',
            password='testpass123',
        )
        self.client.force_login(user)

        upload_response = self.client.get(reverse('imports_app:upload_excel'))
        history_response = self.client.get(reverse('imports_app:history'))

        self.assertEqual(upload_response.status_code, 200)
        self.assertEqual(history_response.status_code, 200)
