import pytest
from django.db import IntegrityError

from apps.imports_app.models import ImportBatch, ImportRowRaw


@pytest.mark.django_db
def test_import_batch_defaults_and_str():
    batch = ImportBatch.objects.create(original_filename='modelo.xlsx')

    assert batch.source_type == ImportBatch.SourceType.MANUAL_EXCEL
    assert batch.status == ImportBatch.Status.PENDING
    assert batch.total_rows == 0
    assert batch.success_rows == 0
    assert batch.duplicate_rows == 0
    assert str(batch) == 'modelo.xlsx (pending)'


@pytest.mark.django_db
def test_import_row_raw_defaults_and_str():
    batch = ImportBatch.objects.create(original_filename='raw.xlsx')
    row = ImportRowRaw.objects.create(
        batch=batch,
        source_row_number=2,
        raw_payload={'name': 'Ana'},
        raw_hash='hash-1',
    )

    assert row.processing_status == ImportRowRaw.ProcessingStatus.IMPORTED
    assert row.processing_error == ''
    assert str(row) == f'Batch {batch.id} row 2'


@pytest.mark.django_db
def test_import_row_unique_constraint_per_batch():
    batch = ImportBatch.objects.create(original_filename='constraint.xlsx')
    ImportRowRaw.objects.create(
        batch=batch,
        source_row_number=2,
        raw_payload={'name': 'Ana'},
        raw_hash='hash-1',
    )

    with pytest.raises(IntegrityError):
        ImportRowRaw.objects.create(
            batch=batch,
            source_row_number=2,
            raw_payload={'name': 'Bruno'},
            raw_hash='hash-2',
        )


@pytest.mark.django_db
def test_import_batch_has_related_raw_rows():
    batch = ImportBatch.objects.create(original_filename='rel.xlsx')
    ImportRowRaw.objects.create(
        batch=batch,
        source_row_number=2,
        raw_payload={'name': 'Ana'},
        raw_hash='hash-1',
    )

    assert batch.raw_rows.count() == 1
