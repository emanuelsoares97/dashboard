from pathlib import Path

from django.db import transaction

from apps.imports_app.models import ImportBatch
from apps.imports_app.parsers.excel_reader import iter_row_payloads, read_excel_dataframe
from apps.imports_app.parsers.row_mapper import build_raw_hash, map_row
from apps.imports_app.persistence.import_writer import create_raw_row, persist_interaction
from apps.imports_app.rules.inconsistencies import detect_inconsistencies
from apps.imports_app.types import ImportSummary
from apps.imports_app.validators.file_validator import validate_required_columns
from apps.imports_app.validators.row_validator import validate_row


def import_excel(file_path: Path, batch: ImportBatch) -> dict:
    dataframe = read_excel_dataframe(file_path)
    validate_required_columns(dataframe.columns)

    summary = ImportSummary(total_rows=len(dataframe))

    with transaction.atomic():
        batch.status = ImportBatch.Status.PROCESSING
        batch.total_rows = summary.total_rows
        batch.save(update_fields=['status', 'total_rows'])

        for row_number, row_payload in iter_row_payloads(dataframe):
            row_data = map_row(row_number, row_payload)
            raw_row = create_raw_row(
                batch=batch,
                row_number=row_data.row_number,
                raw_payload=row_data.raw_payload,
                raw_hash=build_raw_hash(row_data.raw_payload),
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
            except Exception as exc:
                summary.failed_rows += 1
                batch.error_log = f'{batch.error_log}\nLinha {row_number}: {exc}'.strip()

        batch.success_rows = summary.imported_rows
        batch.failed_rows = summary.failed_rows
        batch.flagged_rows = summary.inconsistencies
        batch.status = (
            ImportBatch.Status.PARTIAL
            if summary.imported_rows and summary.failed_rows
            else ImportBatch.Status.SUCCESS
            if summary.imported_rows
            else ImportBatch.Status.FAILED
        )
        batch.notes = (
            f'Linhas importadas: {summary.imported_rows} | '
            f'Flags: {summary.inconsistencies}'
        )
        batch.save(
            update_fields=[
                'success_rows',
                'failed_rows',
                'flagged_rows',
                'status',
                'notes',
                'error_log',
            ]
        )

    return summary.as_dict()
