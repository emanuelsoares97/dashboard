import hashlib
from typing import Any

import pandas as pd

from apps.imports_app.types import ImportRowData


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


def map_row(row_number: int, row: dict[str, Any]) -> ImportRowData:
    raw_payload = build_raw_payload(row)
    return ImportRowData(
        row_number=row_number,
        raw_payload=raw_payload,
        external_call_id=normalize_text(row.get('external_call_id')),
        team_name=normalize_text(row.get('team_name')),
        agent_name=normalize_text(row.get('agent_name')),
        start_at=parse_datetime(row.get('start_date')),
        end_at=parse_datetime(row.get('end_date')),
        ret_resolution=normalize_text(row.get('ret_resolution')),
        resolution=normalize_text(row.get('resolution')),
        third_category=normalize_text(row.get('third_category')),
        service_type=normalize_text(row.get('service_type')),
        is_call_drop=to_bool(row.get('call_drop', '')),
    )
