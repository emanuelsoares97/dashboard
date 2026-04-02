from pathlib import Path

from django.db import transaction
from django.db.models import Prefetch

from apps.imports_app.models import ImportBatch, ImportRowRaw
from apps.imports_app.parsers.excel_reader import iter_row_payloads, read_excel_dataframe
from apps.imports_app.parsers.row_mapper import build_raw_hash, map_row
from apps.imports_app.persistence.import_writer import create_raw_row, persist_interaction
from apps.imports_app.rules.inconsistencies import detect_inconsistencies
from apps.imports_app.types import ImportSummary
from apps.imports_app.validators.file_validator import validate_required_columns
from apps.imports_app.validators.row_validator import validate_row
from apps.quality.models import DataQualityFlag


def list_import_batches(*, page_number=1, per_page=20):
    """Devolve lotes paginados para historico operacional de importacoes."""
    from django.core.paginator import Paginator

    queryset = ImportBatch.objects.all().order_by('-imported_at', '-id')
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(page_number)


def get_import_batch_detail(batch_id: int) -> ImportBatch:
    """Carrega detalhe operacional de um lote com dados necessarios para auditoria."""
    queryset = (
        ImportBatch.objects.select_related('uploaded_by')
        .prefetch_related(
            Prefetch(
                'raw_rows',
                queryset=ImportRowRaw.objects.order_by('source_row_number'),
            )
        )
    )
    return queryset.get(id=batch_id)


def build_batch_detail_context(batch: ImportBatch, *, sample_size=10) -> dict:
    """Monta contexto de detalhe de lote sem colocar logica na view."""
    inconsistency_qs = DataQualityFlag.objects.filter(
        interaction__batch=batch,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
    ).select_related('interaction__agent')

    raw_rows = batch.raw_rows.all()
    return {
        'batch': batch,
        'samples': {
            'duplicate_in_file': raw_rows.filter(
                processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_IN_FILE
            )[:sample_size],
            'duplicate_previous': raw_rows.filter(
                processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_PREVIOUS
            )[:sample_size],
            'failed_rows': raw_rows.filter(
                processing_status=ImportRowRaw.ProcessingStatus.FAILED_VALIDATION
            )[:sample_size],
        },
        'inconsistency_total': inconsistency_qs.count(),
        'inconsistency_samples': inconsistency_qs[:sample_size],
    }


def import_excel(file_path: Path, batch: ImportBatch) -> dict:
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
            row_hash = build_raw_hash(row_data.raw_payload)

            # Evita duplicados no mesmo ficheiro e entre imports anteriores ja processados.
            if row_hash in seen_hashes:
                create_raw_row(
                    batch=batch,
                    row_number=row_data.row_number,
                    raw_payload=row_data.raw_payload,
                    raw_hash=row_hash,
                    processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_IN_FILE,
                    processing_error='Linha duplicada no mesmo ficheiro.',
                )
                summary.duplicate_rows += 1
                summary.duplicate_in_file_rows += 1
                continue
            if ImportRowRaw.objects.filter(raw_hash=row_hash, processed_interaction__isnull=False).exists():
                create_raw_row(
                    batch=batch,
                    row_number=row_data.row_number,
                    raw_payload=row_data.raw_payload,
                    raw_hash=row_hash,
                    processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_PREVIOUS,
                    processing_error='Linha duplicada de importacao anterior.',
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
                raw_row.processing_status = ImportRowRaw.ProcessingStatus.FAILED_VALIDATION
                raw_row.processing_error = str(exc)
                raw_row.save(update_fields=['processing_status', 'processing_error'])
                summary.failed_rows += 1
                batch.error_log = f'{batch.error_log}\nLinha {row_number}: {exc}'.strip()

        batch.success_rows = summary.imported_rows
        batch.duplicate_rows = summary.duplicate_rows
        batch.duplicate_in_file_rows = summary.duplicate_in_file_rows
        batch.duplicate_previous_rows = summary.duplicate_previous_rows
        batch.failed_rows = summary.failed_rows
        batch.flagged_rows = summary.inconsistencies
        has_processed_rows = bool(summary.imported_rows or summary.duplicate_rows)
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

    return summary.as_dict()
