from pathlib import Path
from unittest.mock import patch

import pandas as pd

from apps.imports_app.models import ImportBatch
from apps.imports_app.services import build_batch_detail_context
from apps.imports_app.services import get_import_batch_detail
from apps.imports_app.services import import_excel
from apps.imports_app.services import list_import_batches


def test_list_import_batches_returns_paginated_result(db):
    for index in range(25):
        ImportBatch.objects.create(original_filename=f'batch-{index}.xlsx')

    page_1 = list_import_batches(page_number=1, per_page=20)
    page_2 = list_import_batches(page_number=2, per_page=20)

    assert page_1.paginator.count == 25
    assert len(page_1.object_list) == 20
    assert len(page_2.object_list) == 5


def test_list_import_batches_sorted_by_latest_first(db):
    first = ImportBatch.objects.create(original_filename='old.xlsx')
    second = ImportBatch.objects.create(original_filename='new.xlsx')

    page = list_import_batches(page_number=1, per_page=20)

    assert page.object_list[0].id == second.id
    assert page.object_list[1].id == first.id


def test_services_facade_exports_expected_symbols():
    assert callable(import_excel)
    assert callable(list_import_batches)
    assert callable(get_import_batch_detail)
    assert callable(build_batch_detail_context)


def test_import_excel_keeps_legacy_read_excel_patch_target(db):
    batch = ImportBatch.objects.create(original_filename='compat.xlsx')
    dataframe = pd.DataFrame(columns=['agent_name', 'start_date', 'end_date', 'final_outcome'])

    with patch('apps.imports_app.services.read_excel_dataframe', return_value=dataframe):
        summary = import_excel(Path('fake.xlsx'), batch)

    batch.refresh_from_db()
    assert summary['total_rows'] == 0
    assert batch.total_rows == 0
