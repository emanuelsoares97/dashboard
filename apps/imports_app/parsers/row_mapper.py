import hashlib
from typing import Any

import pandas as pd

from apps.imports_app.types import ImportRowData


SERVICE_TYPE_NORMALIZATION_MAP = {
    'Voz p\u00f3s-paga': 'Voz p\u00f3s-pago',
    'Voz pr\u00e9-paga': 'Voz pr\u00e9-pago',
    'Voz p\u00c3\u00b3s-paga': 'Voz p\u00f3s-pago',
    'Voz pr\u00c3\u00a9-paga': 'Voz pr\u00e9-pago',
}


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ''
    return str(value).strip()


def to_bool(value: Any) -> bool:
    text = normalize_text(value).lower()
    return text in {'1', 'true', 'sim', 'yes', 'call drop'}


def parse_datetime(value: Any):
    if pd.isna(value) or value in (None, ''):
        return None

    try:
        return pd.to_datetime(value).to_pydatetime()
    except (TypeError, ValueError):
        return None


def build_raw_payload(row: dict[str, Any]) -> dict[str, str]:
    return {column: normalize_text(value) for column, value in row.items()}


def build_raw_hash(raw_payload: dict[str, str]) -> str:
    normalized_items = sorted((str(key), str(value)) for key, value in raw_payload.items())
    serialized = '|'.join(f'{key}={value}' for key, value in normalized_items)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def normalize_service_type(value: Any) -> str:
    service_type = normalize_text(value)
    return SERVICE_TYPE_NORMALIZATION_MAP.get(service_type, service_type)


def map_row(row_number: int, row: dict[str, Any]) -> ImportRowData:
    raw_payload = build_raw_payload(row)
    final_outcome = normalize_text(row.get('final_outcome'))

    return ImportRowData(
        row_number=row_number,
        raw_payload=raw_payload,
        external_call_id=normalize_text(row.get('external_call_id')),
        agent_name=normalize_text(row.get('agent_name')),
        start_at=parse_datetime(row.get('start_date')),
        end_at=parse_datetime(row.get('end_date')),
        final_outcome=final_outcome,
        retention_action=normalize_text(row.get('retention_action')),
        churn_reason=normalize_text(row.get('churn_reason')),
        service_type=normalize_service_type(row.get('service_type')),
        is_call_drop=to_bool(final_outcome),
        day=normalize_text(row.get('day')),
        week=normalize_text(row.get('week')),
        month=normalize_text(row.get('month')),
        exclude=normalize_text(row.get('exclude')),
    )
