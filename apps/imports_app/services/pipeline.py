from apps.imports_app.models import ImportBatch, ImportRowRaw
from apps.imports_app.types import ImportSummary
from apps.inbound.models import Interaction


PROGRESS_SAVE_EVERY_ROWS = 200


def _build_client_month_key(row_data):
    external_call_id = (row_data.external_call_id or '').strip()
    if not external_call_id or external_call_id == '1' or row_data.start_at is None:
        return None
    return external_call_id, row_data.start_at.year, row_data.start_at.month


def _row_recency_sort_key(row_data):
    if row_data.start_at is None:
        return (0, 0)
    return (1, row_data.start_at.timestamp())


def _delete_ids_in_chunks(ids_to_delete: list[int], *, chunk_size: int = 1000) -> int:
    deleted_total = 0
    for index in range(0, len(ids_to_delete), chunk_size):
        chunk = ids_to_delete[index:index + chunk_size]
        existing_ids = list(Interaction.objects.filter(id__in=chunk).values_list('id', flat=True))
        if existing_ids:
            Interaction.objects.filter(id__in=existing_ids).delete()
            deleted_total += len(existing_ids)
    return deleted_total


def _consolidate_existing_monthly_duplicates() -> int:
    queryset = (
        Interaction.objects.filter(direction=Interaction.Direction.INBOUND)
        .exclude(call_id_external__isnull=True)
        .exclude(call_id_external='')
        .exclude(call_id_external='1')
        .values('id', 'call_id_external', 'start_at')
        .order_by('call_id_external', '-start_at', '-id')
    )

    seen_keys: set[tuple[str, int, int]] = set()
    ids_to_delete: list[int] = []

    for row in queryset.iterator(chunk_size=2000):
        start_at = row['start_at']
        if start_at is None:
            continue

        key = (row['call_id_external'], start_at.year, start_at.month)
        if key in seen_keys:
            ids_to_delete.append(row['id'])
            continue
        seen_keys.add(key)

    if not ids_to_delete:
        return 0
    return _delete_ids_in_chunks(ids_to_delete)


def _get_existing_latest_for_key(key: tuple[str, int, int]):
    call_id_external, year, month = key
    return (
        Interaction.objects.filter(
            direction=Interaction.Direction.INBOUND,
            call_id_external=call_id_external,
            start_at__year=year,
            start_at__month=month,
        )
        .order_by('-start_at', '-id')
        .first()
    )


def _delete_existing_rows_for_key(key: tuple[str, int, int]) -> int:
    call_id_external, year, month = key
    existing_ids = list(
        Interaction.objects.filter(
        direction=Interaction.Direction.INBOUND,
        call_id_external=call_id_external,
        start_at__year=year,
        start_at__month=month,
    ).values_list('id', flat=True)
    )
    if existing_ids:
        Interaction.objects.filter(id__in=existing_ids).delete()
    return len(existing_ids)


def _select_rows_to_persist(mapped_rows, summary: ImportSummary, *, is_retention_category):
    grouped_by_client_month: dict[tuple[str, int, int], list] = {}
    selected_rows = []

    for row_data in mapped_rows:
        if not is_retention_category(row_data.category):
            summary.skipped_non_retention_rows += 1
            continue

        key = _build_client_month_key(row_data)
        if key is None:
            selected_rows.append(row_data)
            continue

        grouped_by_client_month.setdefault(key, []).append(row_data)

    for _key, group_rows in grouped_by_client_month.items():
        if len(group_rows) == 1:
            selected_rows.append(group_rows[0])
            continue

        sorted_rows = sorted(group_rows, key=_row_recency_sort_key, reverse=True)
        selected_rows.append(sorted_rows[0])
        dropped = len(sorted_rows) - 1
        summary.duplicate_rows += dropped
        summary.duplicate_in_file_rows += dropped

    selected_rows.sort(key=lambda row: row.row_number)
    return selected_rows


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
        f'Consolidadas na base (cliente/mes): {summary.consolidated_existing_rows} | '
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


def _save_processing_progress(*, batch, summary):
    processed_rows = (
        summary.imported_rows
        + summary.duplicate_rows
        + summary.failed_rows
        + summary.skipped_non_retention_rows
    )

    batch.success_rows = summary.imported_rows
    batch.duplicate_rows = summary.duplicate_rows
    batch.duplicate_in_file_rows = summary.duplicate_in_file_rows
    batch.duplicate_previous_rows = summary.duplicate_previous_rows
    batch.failed_rows = summary.failed_rows
    batch.flagged_rows = summary.inconsistencies
    batch.notes = (
        f'PROGRESS|processed={processed_rows}|total={summary.total_rows}|'
        f'skipped={summary.skipped_non_retention_rows}'
    )
    batch.save(
        update_fields=[
            'success_rows',
            'duplicate_rows',
            'duplicate_in_file_rows',
            'duplicate_previous_rows',
            'failed_rows',
            'flagged_rows',
            'notes',
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

    batch.status = ImportBatch.Status.PROCESSING
    batch.total_rows = summary.total_rows
    batch.save(update_fields=['status', 'total_rows'])

    summary.consolidated_existing_rows = _consolidate_existing_monthly_duplicates()

    mapped_rows = []
    for row_number, row_payload in iter_row_payloads(dataframe):
        mapped_rows.append(map_row(row_number, row_payload))

    rows_to_persist = _select_rows_to_persist(
        mapped_rows,
        summary,
        is_retention_category=is_retention_category,
    )

    _save_processing_progress(batch=batch, summary=summary)

    for index, row_data in enumerate(rows_to_persist, start=1):

        row_hash = build_raw_hash(row_data.raw_payload)

        client_month_key = _build_client_month_key(row_data)
        if client_month_key:
            existing_latest = _get_existing_latest_for_key(client_month_key)
            if existing_latest is not None:
                if row_data.start_at is None or existing_latest.start_at >= row_data.start_at:
                    _create_duplicate_previous_row(
                        batch=batch,
                        row_data=row_data,
                        row_hash=row_hash,
                        create_raw_row=create_raw_row,
                    )
                    summary.duplicate_rows += 1
                    summary.duplicate_previous_rows += 1
                    if index % PROGRESS_SAVE_EVERY_ROWS == 0:
                        _save_processing_progress(batch=batch, summary=summary)
                    continue
                summary.consolidated_existing_rows += _delete_existing_rows_for_key(client_month_key)

        if row_hash in seen_hashes:
            _create_duplicate_in_file_row(
                batch=batch,
                row_data=row_data,
                row_hash=row_hash,
                create_raw_row=create_raw_row,
            )
            summary.duplicate_rows += 1
            summary.duplicate_in_file_rows += 1
            if index % PROGRESS_SAVE_EVERY_ROWS == 0:
                _save_processing_progress(batch=batch, summary=summary)
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
            if index % PROGRESS_SAVE_EVERY_ROWS == 0:
                _save_processing_progress(batch=batch, summary=summary)
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
            _handle_failed_row(batch=batch, raw_row=raw_row, row_number=row_data.row_number, exc=exc)
            summary.failed_rows += 1

        if index % PROGRESS_SAVE_EVERY_ROWS == 0:
            _save_processing_progress(batch=batch, summary=summary)

    _save_processing_progress(batch=batch, summary=summary)
    _finalize_batch(batch=batch, summary=summary)

    return summary.as_dict()