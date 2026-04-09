from pathlib import Path
from unittest.mock import patch

import pandas as pd
from django.test import TestCase

from apps.imports_app.models import ImportBatch, ImportRowRaw
from apps.imports_app.services import import_excel
from apps.inbound.models import Interaction


class ImportExcelServiceTests(TestCase):
    def _make_batch(self, filename='test.xlsx'):
        return ImportBatch.objects.create(
            original_filename=filename,
            source_type=ImportBatch.SourceType.MANUAL_EXCEL,
        )

    def _run_import(self, batch, rows):
        dataframe = pd.DataFrame(rows)
        with patch('apps.imports_app.services.read_excel_dataframe', return_value=dataframe):
            return import_excel(Path('fake.xlsx'), batch)

    def test_imports_new_rows_successfully(self):
        batch = self._make_batch()
        summary = self._run_import(
            batch,
            [
                {
                    'external_call_id': 'c1',
                    'agent_name': 'Ana',
                    'start_date': '2026-01-01T10:00:00Z',
                    'end_date': '2026-01-01T10:10:00Z',
                    'final_outcome': 'Retido',
                    'retention_action': 'Oferta',
                    'category': 'Retencao',
                    'churn_reason': 'Preco',
                    'service_type': 'Fibra',
                    'day': '2026-01-01',
                    'week': '2026-W01',
                    'month': '2026-01',
                    'exclude': '',
                }
            ],
        )

        batch.refresh_from_db()
        self.assertEqual(summary['imported_rows'], 1)
        self.assertEqual(summary['skipped_non_retention_rows'], 0)
        self.assertEqual(summary['consolidated_existing_rows'], 0)
        self.assertEqual(summary['duplicate_rows'], 0)
        self.assertEqual(summary['failed_rows'], 0)
        self.assertEqual(Interaction.objects.filter(batch=batch).count(), 1)
        self.assertEqual(batch.success_rows, 1)
        self.assertEqual(batch.status, ImportBatch.Status.SUCCESS)

    def test_ignores_duplicates_from_previous_import(self):
        first_batch = self._make_batch('first.xlsx')
        second_batch = self._make_batch('second.xlsx')
        rows = [
            {
                'external_call_id': 'c2',
                'agent_name': 'Bruno',
                'start_date': '2026-01-01T11:00:00Z',
                'end_date': '2026-01-01T11:08:00Z',
                'final_outcome': 'Retido',
                'retention_action': 'Plano B',
                'category': 'Retencao',
                'churn_reason': 'Preco',
                'service_type': 'Movel',
                'day': '2026-01-01',
                'week': '2026-W01',
                'month': '2026-01',
                'exclude': '',
            }
        ]

        self._run_import(first_batch, rows)
        summary = self._run_import(second_batch, rows)
        second_batch.refresh_from_db()

        self.assertEqual(summary['imported_rows'], 0)
        self.assertEqual(summary['skipped_non_retention_rows'], 0)
        self.assertEqual(summary['consolidated_existing_rows'], 0)
        self.assertEqual(summary['duplicate_rows'], 1)
        self.assertEqual(summary['duplicate_previous_rows'], 1)
        self.assertEqual(second_batch.duplicate_previous_rows, 1)
        self.assertEqual(
            ImportRowRaw.objects.filter(
                batch=second_batch,
                processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_PREVIOUS,
            ).count(),
            1,
        )

    def test_ignores_duplicates_inside_same_file(self):
        batch = self._make_batch()
        duplicate_row = {
            'external_call_id': 'c3',
            'agent_name': 'Carla',
            'start_date': '2026-01-02T09:00:00Z',
            'end_date': '2026-01-02T09:07:00Z',
            'final_outcome': 'Retido',
            'retention_action': 'Pendente',
            'category': 'Retencao',
            'churn_reason': 'Preco',
            'service_type': 'TV',
            'day': '2026-01-02',
            'week': '2026-W01',
            'month': '2026-01',
            'exclude': '',
        }

        summary = self._run_import(batch, [duplicate_row, duplicate_row])
        batch.refresh_from_db()

        self.assertEqual(summary['imported_rows'], 1)
        self.assertEqual(summary['skipped_non_retention_rows'], 0)
        self.assertEqual(summary['consolidated_existing_rows'], 0)
        self.assertEqual(summary['duplicate_rows'], 1)
        self.assertEqual(summary['duplicate_in_file_rows'], 1)
        self.assertEqual(batch.duplicate_in_file_rows, 1)

    def test_handles_mixed_new_duplicate_and_invalid_rows(self):
        previous_batch = self._make_batch('previous.xlsx')
        self._run_import(
            previous_batch,
            [
                {
                    'external_call_id': 'c4',
                    'agent_name': 'Diogo',
                    'start_date': '2026-01-03T09:00:00Z',
                    'end_date': '2026-01-03T09:09:00Z',
                    'final_outcome': 'Retido',
                    'retention_action': 'Oferta',
                    'category': 'Retencao',
                    'churn_reason': 'Preco',
                    'service_type': 'Fibra',
                    'day': '2026-01-03',
                    'week': '2026-W01',
                    'month': '2026-01',
                    'exclude': '',
                }
            ],
        )

        batch = self._make_batch('mixed.xlsx')
        summary = self._run_import(
            batch,
            [
                {
                    'external_call_id': 'c5',
                    'agent_name': 'Eva',
                    'start_date': '2026-01-04T10:00:00Z',
                    'end_date': '2026-01-04T10:06:00Z',
                    'final_outcome': 'Retido',
                    'retention_action': 'Oferta',
                    'category': 'Retencao',
                    'churn_reason': 'Servico',
                    'service_type': 'Fibra',
                    'day': '2026-01-04',
                    'week': '2026-W01',
                    'month': '2026-01',
                    'exclude': '',
                },
                {
                    'external_call_id': 'c4',
                    'agent_name': 'Diogo',
                    'start_date': '2026-01-03T09:00:00Z',
                    'end_date': '2026-01-03T09:09:00Z',
                    'final_outcome': 'Retido',
                    'retention_action': 'Oferta',
                    'category': 'Retencao',
                    'churn_reason': 'Preco',
                    'service_type': 'Fibra',
                    'day': '2026-01-03',
                    'week': '2026-W01',
                    'month': '2026-01',
                    'exclude': '',
                },
                {
                    'external_call_id': 'c5',
                    'agent_name': 'Eva',
                    'start_date': '2026-01-04T10:00:00Z',
                    'end_date': '2026-01-04T10:06:00Z',
                    'final_outcome': 'Retido',
                    'retention_action': 'Oferta',
                    'category': 'Retencao',
                    'churn_reason': 'Servico',
                    'service_type': 'Fibra',
                    'day': '2026-01-04',
                    'week': '2026-W01',
                    'month': '2026-01',
                    'exclude': '',
                },
                {
                    'external_call_id': 'c6',
                    'agent_name': '',
                    'start_date': '2026-01-04T11:00:00Z',
                    'end_date': '2026-01-04T11:05:00Z',
                    'final_outcome': 'Retido',
                    'retention_action': 'Oferta',
                    'category': 'Retencao',
                    'churn_reason': 'Preco',
                    'service_type': 'TV',
                    'day': '2026-01-04',
                    'week': '2026-W01',
                    'month': '2026-01',
                    'exclude': '',
                },
            ],
        )

        batch.refresh_from_db()
        self.assertEqual(summary['imported_rows'], 1)
        self.assertEqual(summary['skipped_non_retention_rows'], 0)
        self.assertEqual(summary['consolidated_existing_rows'], 0)
        self.assertEqual(summary['duplicate_rows'], 2)
        self.assertEqual(summary['duplicate_previous_rows'], 1)
        self.assertEqual(summary['duplicate_in_file_rows'], 1)
        self.assertEqual(summary['failed_rows'], 1)
        self.assertEqual(batch.success_rows, 1)
        self.assertEqual(batch.duplicate_rows, 2)
        self.assertEqual(batch.failed_rows, 1)
        self.assertEqual(batch.status, ImportBatch.Status.PARTIAL)

        failed_rows = ImportRowRaw.objects.filter(
            batch=batch,
            processing_status=ImportRowRaw.ProcessingStatus.FAILED_VALIDATION,
        )
        self.assertEqual(failed_rows.count(), 1)

    def test_skips_non_retention_rows_and_does_not_create_interaction(self):
        batch = self._make_batch('skip-non-retention.csv')
        summary = self._run_import(
            batch,
            [
                {
                    'external_call_id': 'nr-1',
                    'agent_name': 'Ana',
                    'start_date': '2026-01-01T10:00:00Z',
                    'end_date': '2026-01-01T10:10:00Z',
                    'retention_action': 'Resolvido',
                    'category': 'CC Informativo',
                },
                {
                    'external_call_id': 'ret-1',
                    'agent_name': 'Ana',
                    'start_date': '2026-01-01T11:00:00Z',
                    'end_date': '2026-01-01T11:05:00Z',
                    'retention_action': 'Nao Retido',
                    'category': 'CC RET Outbound',
                },
            ],
        )

        batch.refresh_from_db()
        self.assertEqual(summary['imported_rows'], 1)
        self.assertEqual(summary['skipped_non_retention_rows'], 1)
        self.assertEqual(summary['consolidated_existing_rows'], 0)
        self.assertEqual(Interaction.objects.filter(batch=batch).count(), 1)
        self.assertIn('Fora de retencao ignoradas: 1', batch.notes)

    def test_replaces_existing_older_row_same_client_month(self):
        first_batch = self._make_batch('first-month.csv')
        second_batch = self._make_batch('second-month.csv')

        self._run_import(
            first_batch,
            [
                {
                    'external_call_id': 'replace-1',
                    'agent_name': 'Ana',
                    'start_date': '2026-01-01T10:00:00Z',
                    'end_date': '2026-01-01T10:05:00Z',
                    'retention_action': 'Nao Retido',
                    'category': 'CC RET Outbound',
                }
            ],
        )

        summary = self._run_import(
            second_batch,
            [
                {
                    'external_call_id': 'replace-1',
                    'agent_name': 'Ana',
                    'start_date': '2026-01-20T10:00:00Z',
                    'end_date': '2026-01-20T10:03:00Z',
                    'retention_action': 'Retido Migracao Pre Pago',
                    'category': 'CC RET Outbound',
                }
            ],
        )

        second_batch.refresh_from_db()
        self.assertEqual(summary['imported_rows'], 1)
        self.assertEqual(summary['consolidated_existing_rows'], 1)
        self.assertIn('Consolidadas na base (cliente/mes): 1', second_batch.notes)
