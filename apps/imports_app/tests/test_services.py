from apps.imports_app.models import ImportBatch
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
