from pathlib import Path

import pandas as pd
from django.db import transaction

from apps.imports_app.models import ImportBatch
from apps.inbound.models import CallRecord
from apps.quality.models import TipificationInconsistency


COLUMN_ALIASES = {
    'external_call_id': ['external_call_id', 'call_id', 'id_chamada'],
    'team_name': ['team_name', 'team', 'equipe'],
    'agent_name': ['agent_name', 'agent', 'atendente'],
    'start_date': ['startdate', 'start_date', 'inicio', 'data_inicio'],
    'end_date': ['enddate', 'end_date', 'fim', 'data_fim'],
    'ret_resolution': ['ret_resolution', 'ret resolution', 'ret_resolucao'],
    'resolution': ['resolution', 'resolucao'],
    'third_category': ['third_category', '3rd_category', 'motivo_churn'],
    'service_type': ['service_type', 'tipo_servico'],
    'call_drop': ['call_drop', 'queda_ligacao'],
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    normalized = {c: c.strip().lower().replace(' ', '_') for c in df.columns}

    for original, normalized_name in normalized.items():
        for target, aliases in COLUMN_ALIASES.items():
            if normalized_name in aliases:
                renamed[original] = target
                break

    return df.rename(columns=renamed)


def to_bool(value) -> bool:
    text = str(value).strip().lower()
    return text in {'1', 'true', 'sim', 'yes', 'call drop'}


def import_excel(file_path: Path, batch: ImportBatch) -> dict:
    df = pd.read_excel(file_path)
    df = normalize_columns(df)

    required = ['team_name', 'agent_name', 'start_date', 'end_date', 'ret_resolution', 'resolution']
    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f'Colunas obrigatorias ausentes: {", ".join(missing)}')

    total_rows = len(df)

    with transaction.atomic():
        batch.status = ImportBatch.Status.PROCESSING
        batch.total_rows = total_rows
        batch.save(update_fields=['status', 'total_rows'])

        call_records = []
        for idx, row in df.iterrows():
            start_date = pd.to_datetime(row.get('start_date'))
            end_date = pd.to_datetime(row.get('end_date'))
            call_records.append(
                CallRecord(
                    external_call_id=str(row.get('external_call_id', '') or ''),
                    team_name=str(row.get('team_name', '') or ''),
                    agent_name=str(row.get('agent_name', '') or ''),
                    start_date=start_date.to_pydatetime(),
                    end_date=end_date.to_pydatetime(),
                    ret_resolution=str(row.get('ret_resolution', '') or ''),
                    resolution=str(row.get('resolution', '') or ''),
                    third_category=str(row.get('third_category', '') or ''),
                    service_type=str(row.get('service_type', '') or ''),
                    call_drop=to_bool(row.get('call_drop', '')),
                    source_file_row=idx + 2,
                    batch=batch,
                )
            )

        created = CallRecord.objects.bulk_create(call_records)

        inconsistencies = []
        for call in created:
            if call.resolution.strip().lower() == 'pendente' and call.ret_resolution.strip().lower() == 'retido':
                inconsistencies.append(
                    TipificationInconsistency(
                        call=call,
                        reason='resolution=Pendente and Ret Resolution=Retido',
                    )
                )

        TipificationInconsistency.objects.bulk_create(inconsistencies)

        batch.imported_rows = len(created)
        batch.status = ImportBatch.Status.DONE
        batch.notes = f'Inconsistencias detectadas: {len(inconsistencies)}'
        batch.save(update_fields=['imported_rows', 'status', 'notes'])

    return {
        'total_rows': total_rows,
        'imported_rows': len(created),
        'inconsistencies': len(inconsistencies),
    }
