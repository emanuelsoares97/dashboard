from pathlib import Path
from unittest.mock import patch

import pandas as pd

from apps.imports_app.models import ImportBatch
from apps.imports_app.services import import_excel


def _run_import(batch, rows):
    dataframe = pd.DataFrame(rows)
    with patch('apps.imports_app.services.read_excel_dataframe', return_value=dataframe):
        return import_excel(Path('fake.xlsx'), batch)


def _base_row(call_id='c1'):
    return {
        'external_call_id': call_id,
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


def test_deduplicates_rows_inside_same_file(db):
    batch = ImportBatch.objects.create(original_filename='same.xlsx')

    summary = _run_import(batch, [_base_row('c1'), _base_row('c1')])

    assert summary['imported_rows'] == 1
    assert summary['duplicate_rows'] == 1
    assert summary['duplicate_in_file_rows'] == 1
    assert summary['duplicate_previous_rows'] == 0


def test_deduplicates_rows_from_previous_import(db):
    first = ImportBatch.objects.create(original_filename='first.xlsx')
    second = ImportBatch.objects.create(original_filename='second.xlsx')

    _run_import(first, [_base_row('c2')])
    summary = _run_import(second, [_base_row('c2')])

    assert summary['imported_rows'] == 0
    assert summary['duplicate_rows'] == 1
    assert summary['duplicate_previous_rows'] == 1
    assert summary['duplicate_in_file_rows'] == 0
