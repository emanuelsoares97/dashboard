from pathlib import Path
from unittest.mock import patch

import pandas as pd

from apps.imports_app.models import ImportBatch
from apps.imports_app.services import import_excel


def _run_import(batch, rows):
    dataframe = pd.DataFrame(rows)
    with patch('apps.imports_app.services.read_excel_dataframe', return_value=dataframe):
        return import_excel(Path('fake.xlsx'), batch)


def _run_import_with_columns(batch, *, columns):
    dataframe = pd.DataFrame(columns=columns)
    with patch('apps.imports_app.services.read_excel_dataframe', return_value=dataframe):
        return import_excel(Path('fake.xlsx'), batch)


def test_pipeline_imports_valid_and_fails_invalid_rows(db):
    batch = ImportBatch.objects.create(original_filename='pipeline.xlsx')

    rows = [
        {
            'external_call_id': 'ok-1',
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
        },
        {
            'external_call_id': 'bad-1',
            'agent_name': '',
            'start_date': '2026-01-01T11:00:00Z',
            'end_date': '2026-01-01T11:05:00Z',
            'final_outcome': 'Retido',
            'retention_action': 'Oferta',
            'category': 'Retencao',
            'churn_reason': 'Preco',
            'service_type': 'Fibra',
            'day': '2026-01-01',
            'week': '2026-W01',
            'month': '2026-01',
            'exclude': '',
        },
    ]

    summary = _run_import(batch, rows)
    batch.refresh_from_db()

    assert summary['total_rows'] == 2
    assert summary['imported_rows'] == 1
    assert summary['skipped_non_retention_rows'] == 0
    assert summary['failed_rows'] == 1
    assert summary['duplicate_rows'] == 0
    assert batch.success_rows == 1
    assert batch.failed_rows == 1
    assert batch.status == ImportBatch.Status.PARTIAL


def test_pipeline_summary_handles_mixed_rows(db):
    previous = ImportBatch.objects.create(original_filename='previous.xlsx')
    current = ImportBatch.objects.create(original_filename='current.xlsx')

    row_a = {
        'external_call_id': 'mix-1',
        'agent_name': 'Ana',
        'start_date': '2026-01-02T10:00:00Z',
        'end_date': '2026-01-02T10:10:00Z',
        'final_outcome': 'Retido',
        'retention_action': 'Oferta',
        'category': 'Retencao',
        'churn_reason': 'Preco',
        'service_type': 'Fibra',
        'day': '2026-01-02',
        'week': '2026-W01',
        'month': '2026-01',
        'exclude': '',
    }
    row_b = {
        'external_call_id': 'mix-2',
        'agent_name': '',
        'start_date': '2026-01-02T12:00:00Z',
        'end_date': '2026-01-02T12:02:00Z',
        'final_outcome': 'Retido',
        'retention_action': 'Oferta',
        'category': 'Retencao',
        'churn_reason': 'Preco',
        'service_type': 'Fibra',
        'day': '2026-01-02',
        'week': '2026-W01',
        'month': '2026-01',
        'exclude': '',
    }

    _run_import(previous, [row_a])
    summary = _run_import(current, [row_a, row_a, row_b])
    current.refresh_from_db()

    assert summary['imported_rows'] == 0
    assert summary['skipped_non_retention_rows'] == 0
    assert summary['duplicate_rows'] == 2
    assert summary['duplicate_previous_rows'] == 2
    assert summary['duplicate_in_file_rows'] == 0
    assert summary['failed_rows'] == 1
    assert current.duplicate_rows == 2
    assert current.duplicate_previous_rows == 2
    assert current.failed_rows == 1
    assert current.status == ImportBatch.Status.PARTIAL


def test_pipeline_with_empty_file_sets_failed_and_no_writes(db):
    batch = ImportBatch.objects.create(original_filename='empty.xlsx')

    summary = _run_import_with_columns(
        batch,
        columns=['agent_name', 'start_date', 'end_date', 'final_outcome'],
    )
    batch.refresh_from_db()

    assert summary['total_rows'] == 0
    assert summary['imported_rows'] == 0
    assert summary['skipped_non_retention_rows'] == 0
    assert summary['failed_rows'] == 0
    assert summary['duplicate_rows'] == 0
    assert batch.total_rows == 0
    assert batch.success_rows == 0
    assert batch.failed_rows == 0
    assert batch.status == ImportBatch.Status.FAILED


def test_pipeline_skips_non_retention_rows_before_persisting(db):
    batch = ImportBatch.objects.create(original_filename='non-retention.csv')

    rows = [
        {
            'external_call_id': 'skip-1',
            'agent_name': 'Ana',
            'start_date': '2026-01-01T10:00:00Z',
            'end_date': '2026-01-01T10:10:00Z',
            'retention_action': 'Resolvido',
            'category': 'CC Informativo',
        },
        {
            'external_call_id': 'keep-1',
            'agent_name': 'Ana',
            'start_date': '2026-01-01T11:00:00Z',
            'end_date': '2026-01-01T11:05:00Z',
            'retention_action': 'Nao Retido',
            'category': 'CC RET Outbound',
        },
    ]

    summary = _run_import(batch, rows)
    batch.refresh_from_db()

    assert summary['total_rows'] == 2
    assert summary['imported_rows'] == 1
    assert summary['skipped_non_retention_rows'] == 1
    assert batch.success_rows == 1
    assert batch.status == ImportBatch.Status.SUCCESS
