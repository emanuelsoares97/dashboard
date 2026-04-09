from django.db import transaction

from apps.imports_app.models import ImportBatch, ImportRowRaw
from apps.imports_app.types import ImportSummary


def _create_duplicate_in_file_row(*, batch, row_data, row_hash, create_raw_row):
    return create_raw_row(
        batch=batch,
        row_number=row_data.row_number,
        raw_payload=row_data.raw_payload,
        raw_hash=row_hash,
        processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_IN_FILE,
        processing_error='Linha duplicada no mesmo ficheiro.',
    )


def _create_duplicate_previous_row(*, batch, row_data, row_hash, create_raw_row):
    return create_raw_row(
        batch=batch,
        row_number=row_data.row_number,
        raw_payload=row_data.raw_payload,
        raw_hash=row_hash,
        processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_PREVIOUS,
        processing_error='Linha duplicada de importacao anterior.',
    )


def _handle_failed_row(*, batch, raw_row, row_number, exc):
    raw_row.processing_status = ImportRowRaw.ProcessingStatus.FAILED_VALIDATION
    raw_row.processing_error = str(exc)
    raw_row.save(update_fields=['processing_status', 'processing_error'])
    batch.error_log = f'{batch.error_log}\nLinha {row_number}: {exc}'.strip()


def _finalize_batch(*, batch, summary):
    batch.success_rows = summary.imported_rows
    batch.duplicate_rows = summary.duplicate_rows
    batch.duplicate_in_file_rows = summary.duplicate_in_file_rows
    batch.duplicate_previous_rows = summary.duplicate_previous_rows
    batch.failed_rows = summary.failed_rows
    batch.flagged_rows = summary.inconsistencies
    has_processed_rows = bool(
        summary.imported_rows or summary.duplicate_rows or summary.skipped_non_retention_rows
    )
    has_failures = bool(summary.failed_rows)
    batch.status = (
        ImportBatch.Status.PARTIAL
        if has_processed_rows and has_failures
        else ImportBatch.Status.SUCCESS
        if has_processed_rows
        else ImportBatch.Status.FAILED
    )
    batch.notes = (
        f'Linhas importadas: {summary.imported_rows} | '
        f'Fora de retencao ignoradas: {summary.skipped_non_retention_rows} | '
        f'Duplicadas ignoradas: {summary.duplicate_rows} | '
        f'Dup. mesmo ficheiro: {summary.duplicate_in_file_rows} | '
        f'Dup. import anterior: {summary.duplicate_previous_rows} | '
        f'Flags: {summary.inconsistencies}'
    )
    batch.save(
        update_fields=[
            'success_rows',
            'duplicate_rows',
            'duplicate_in_file_rows',
            'duplicate_previous_rows',
            'failed_rows',
            'flagged_rows',
            'status',
            'notes',
            'error_log',
        ]
    )


def run_import_excel(
    file_path,
    batch,
    *,
    read_excel_dataframe,
    validate_required_columns,
    iter_row_payloads,
    map_row,
    build_raw_hash,
    create_raw_row,
    validate_row,
    detect_inconsistencies,
    persist_interaction,
    is_retention_category,
):
    dataframe = read_excel_dataframe(file_path)
    validate_required_columns(dataframe.columns)

    summary = ImportSummary(total_rows=len(dataframe))
    seen_hashes: set[str] = set()

    with transaction.atomic():
        batch.status = ImportBatch.Status.PROCESSING
        batch.total_rows = summary.total_rows
        batch.save(update_fields=['status', 'total_rows'])

        for row_number, row_payload in iter_row_payloads(dataframe):
            row_data = map_row(row_number, row_payload)

            if not is_retention_category(row_data.category):
                summary.skipped_non_retention_rows += 1
                continue

            row_hash = build_raw_hash(row_data.raw_payload)

            if row_hash in seen_hashes:
                _create_duplicate_in_file_row(
                    batch=batch,
                    row_data=row_data,
                    row_hash=row_hash,
                    create_raw_row=create_raw_row,
                )
                summary.duplicate_rows += 1
                summary.duplicate_in_file_rows += 1
                continue

            if ImportRowRaw.objects.filter(raw_hash=row_hash, processed_interaction__isnull=False).exists():
                _create_duplicate_previous_row(
                    batch=batch,
                    row_data=row_data,
                    row_hash=row_hash,
                    create_raw_row=create_raw_row,
                )
                summary.duplicate_rows += 1
                summary.duplicate_previous_rows += 1
                continue

            raw_row = create_raw_row(
                batch=batch,
                row_number=row_data.row_number,
                raw_payload=row_data.raw_payload,
                raw_hash=row_hash,
            )

            try:
                validation_result = validate_row(row_data)
                if not validation_result.is_valid:
                    raise ValueError('; '.join(validation_result.errors))

                quality_flags = detect_inconsistencies(validation_result.row_data)
                _, created_flags = persist_interaction(
                    batch=batch,
                    raw_row=raw_row,
                    row_data=validation_result.row_data,
                    quality_flags=quality_flags,
                )

                summary.imported_rows += 1
                summary.inconsistencies += created_flags
                seen_hashes.add(row_hash)
            except Exception as exc:
                _handle_failed_row(batch=batch, raw_row=raw_row, row_number=row_number, exc=exc)
                summary.failed_rows += 1

        _finalize_batch(batch=batch, summary=summary)

    return summary.as_dict()