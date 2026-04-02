from pathlib import Path

import pytest

from apps.imports_app.parsers.excel_reader import read_excel_dataframe
from apps.imports_app.parsers.row_mapper import map_row, normalize_text


def test_read_excel_dataframe_raises_for_invalid_file_path():
    with pytest.raises(FileNotFoundError):
        read_excel_dataframe(Path('ficheiro_inexistente.xlsx'))


def test_map_row_normalizes_text_and_invalid_datetime():
    row = {
        'external_call_id': '  C-10  ',
        'agent_name': '  Ana  ',
        'start_date': 'invalid-date',
        'end_date': '2026-01-01T10:10:00Z',
        'final_outcome': '  Call Drop  ',
        'retention_action': '  Oferta ',
        'churn_reason': '  Preco ',
        'service_type': '  Fibra ',
        'day': ' 2026-01-01 ',
        'week': ' 2026-W01 ',
        'month': ' 2026-01 ',
        'exclude': ' ',
    }

    mapped = map_row(2, row)

    assert mapped.external_call_id == 'C-10'
    assert mapped.agent_name == 'Ana'
    assert mapped.start_at is None
    assert mapped.end_at is not None
    assert mapped.final_outcome == 'Call Drop'
    assert mapped.is_call_drop is True


def test_normalize_text_handles_none_and_spaces():
    assert normalize_text(None) == ''
    assert normalize_text('  abc  ') == 'abc'
