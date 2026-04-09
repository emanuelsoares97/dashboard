from pathlib import Path

import pytest

from apps.imports_app.parsers.excel_reader import read_excel_dataframe
from apps.imports_app.parsers.row_mapper import is_retention_category, map_row, normalize_ret_resolution, normalize_text, normalize_service_type


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


def test_map_row_derives_final_outcome_from_resolution_when_missing():
    row = {
        'external_call_id': 'C-20',
        'agent_name': 'Ana',
        'start_date': '2026-01-01T10:00:00Z',
        'end_date': '2026-01-01T10:10:00Z',
        'category': 'CC RET Pedido de desativacao',
        'retention_action': 'Retido Explicacao Servicos',
        'service_type': 'Fibra',
    }

    mapped = map_row(2, row)

    assert mapped.retention_action == 'Retido Explicacao Servicos'
    assert mapped.final_outcome == 'Retido'
    assert mapped.is_call_drop is False


def test_map_row_uses_generic_outcome_outside_retention_categories():
    row = {
        'external_call_id': 'C-21',
        'agent_name': 'Ana',
        'start_date': '2026-01-01T10:00:00Z',
        'end_date': '2026-01-01T10:10:00Z',
        'category': 'CC Informativo',
        'retention_action': 'Nao Retido',
    }

    mapped = map_row(2, row)

    assert mapped.final_outcome == 'Resolvido fora de retencao'


def test_normalize_text_handles_none_and_spaces():
    assert normalize_text(None) == ''
    assert normalize_text('  abc  ') == 'abc'


@pytest.mark.parametrize(
    ('source_label', 'expected_label'),
    [
        ('Voz p\u00f3s-paga', 'Voz p\u00f3s-pago'),
        ('Voz pr\u00e9-paga', 'Voz pr\u00e9-pago'),
        ('Voz p\u00c3\u00b3s-paga', 'Voz p\u00f3s-pago'),
        ('Voz pr\u00c3\u00a9-paga', 'Voz pr\u00e9-pago'),
    ],
)
def test_normalize_service_type_applies_expected_aliases(source_label, expected_label):
    assert normalize_service_type(source_label) == expected_label


@pytest.mark.parametrize(
    ('raw_value', 'expected'),
    [
        ('Nao Retido', 'Nao Retido'),
        ('Retido Migracao Pre Pago', 'Retido'),
        ('Pendente', 'Pendente'),
        ('Chamada Caiu', 'Call Drop'),
        ('Encaminhado Email /Ticket', 'Encaminhado'),
        ('Contacto sem sucesso', 'Call Drop'),
        ('N\u00e3o Aceita Resolu\u00e7\u00e3o', 'Nao Retido'),
        ('resolved', 'Resolvido fora de retencao'),
    ],
)
def test_normalize_ret_resolution_maps_new_csv_values(raw_value, expected):
    assert normalize_ret_resolution(raw_value, is_retention_case=True) == expected


def test_normalize_ret_resolution_outside_retention_category_is_generic():
    assert normalize_ret_resolution('Nao Retido', is_retention_case=False) == 'Resolvido fora de retencao'
    assert normalize_ret_resolution('Encaminhado Email /Ticket', is_retention_case=False) == 'Encaminhado'


@pytest.mark.parametrize(
    ('category', 'expected'),
    [
        ('Retencao', True),
        ('CC RET Pedido de desativacao', True),
        ('CC RET Outbound', True),
        ('CC RET Desiste da adesao', True),
        ('CC Informativo', False),
        ('CC Tecnico', False),
        ('', False),
    ],
)
def test_is_retention_category_matches_real_csv_patterns(category, expected):
    assert is_retention_category(category) is expected
