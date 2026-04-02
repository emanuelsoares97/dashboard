from datetime import datetime, timezone

import pytest

from apps.imports_app.types import ImportRowData
from apps.imports_app.validators.file_validator import validate_required_columns
from apps.imports_app.validators.row_validator import validate_row


def _row(**overrides):
    payload = {
        'row_number': 2,
        'raw_payload': {},
        'external_call_id': 'c-1',
        'agent_name': 'Ana',
        'start_at': datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        'end_at': datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc),
        'final_outcome': 'Retido',
        'retention_action': 'Oferta',
        'churn_reason': 'Preco',
        'service_type': 'Fibra',
        'is_call_drop': False,
        'day': '2026-01-01',
        'week': '2026-W01',
        'month': '2026-01',
        'exclude': '',
    }
    payload.update(overrides)
    return ImportRowData(**payload)


def test_validate_required_columns_raises_with_missing_and_hint():
    with pytest.raises(ValueError) as exc:
        validate_required_columns(['agent_name', 'start_date', 'endDate'])

    message = str(exc.value)
    assert 'end_date' in message
    assert 'final_outcome' in message
    assert "Esperado: 'enddate'" in message
    assert "Esperado: 'Ret Resolution'" in message


def test_validate_required_columns_accepts_valid_schema():
    validate_required_columns(['agent_name', 'start_date', 'end_date', 'final_outcome'])


def test_validate_row_detects_invalid_dates_and_missing_outcome():
    result = validate_row(
        _row(start_at=None, end_at=None, final_outcome='')
    )

    assert not result.is_valid
    assert 'startDate is invalid or missing' in result.errors
    assert 'enddate is invalid or missing' in result.errors
    assert 'Ret Resolution is required' in result.errors


def test_validate_row_detects_end_before_start():
    result = validate_row(
        _row(
            start_at=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
    )

    assert not result.is_valid
    assert 'enddate must be after startDate' in result.errors


def test_validate_row_accepts_valid_row():
    result = validate_row(_row())

    assert result.is_valid
    assert result.errors == []
