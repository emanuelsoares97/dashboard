"""Testes para apps/imports_app/rules/inconsistencies.py."""
from datetime import datetime, timezone

import pytest

from apps.imports_app.rules.inconsistencies import detect_inconsistencies
from apps.imports_app.types import ImportRowData
from apps.quality.models import DataQualityFlag


def _make_row_data(**overrides) -> ImportRowData:
    defaults = dict(
        row_number=1,
        raw_payload={},
        external_call_id='call-1',
        agent_name='Ana',
        start_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc),
        final_outcome='Retido',
        retention_action='Oferta',
        churn_reason='Preco',
        service_type='Fibra',
        is_call_drop=False,
        day='2026-01-01',
        week='2026-W01',
        month='2026-01',
        exclude='',
        category='Retencao',
        subcategory='',
        observations='',
    )
    defaults.update(overrides)
    return ImportRowData(**defaults)


def test_no_flags_for_valid_row():
    row = _make_row_data()
    flags = detect_inconsistencies(row)
    assert flags == []


def test_pending_with_retained_outcome_generates_tipification_flag():
    row = _make_row_data(retention_action='Pendente', final_outcome='Retido')
    flags = detect_inconsistencies(row)

    rule_codes = [f.rule_code for f in flags]
    assert 'pending_resolution_with_retained_outcome' in rule_codes


def test_outcome_value_in_retention_action_generates_error_flag():
    """retention_action='Nao Retido' deve gerar flag de erro de dominio."""
    row = _make_row_data(retention_action='Nao Retido', final_outcome='Nao Retido')
    flags = detect_inconsistencies(row)

    error_flags = [f for f in flags if f.rule_code == 'outcome_value_in_retention_action']
    assert len(error_flags) == 1
    assert error_flags[0].severity == DataQualityFlag.Severity.ERROR
    assert error_flags[0].flag_type == DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY


def test_retido_in_retention_action_generates_error_flag():
    """retention_action='Retido' (valor de outcome) deve gerar flag de erro de dominio."""
    row = _make_row_data(retention_action='Retido', final_outcome='Retido')
    flags = detect_inconsistencies(row)

    rule_codes = [f.rule_code for f in flags]
    assert 'outcome_value_in_retention_action' in rule_codes


def test_call_drop_in_retention_action_generates_error_flag():
    row = _make_row_data(retention_action='Call Drop', final_outcome='Call Drop', is_call_drop=True)
    flags = detect_inconsistencies(row)

    rule_codes = [f.rule_code for f in flags]
    assert 'outcome_value_in_retention_action' in rule_codes


def test_outcome_value_detection_is_case_insensitive():
    """A detecao de outcome em retention_action deve ser case-insensitive."""
    for variant in ('nao retido', 'NAO RETIDO', 'Nao Retido', 'NAo ReTiDo'):
        row = _make_row_data(retention_action=variant)
        flags = detect_inconsistencies(row)
        rule_codes = [f.rule_code for f in flags]
        assert 'outcome_value_in_retention_action' in rule_codes, (
            f'Esperava flag para retention_action="{variant}"'
        )


def test_regular_action_does_not_generate_outcome_domain_flag():
    """Acoes legítimas nao devem gerar o flag de dominio de outcome."""
    for valid_action in ('Oferta', 'Negociacao', 'Pendente', 'Plano B', 'Desconto'):
        row = _make_row_data(retention_action=valid_action)
        flags = detect_inconsistencies(row)
        rule_codes = [f.rule_code for f in flags]
        assert 'outcome_value_in_retention_action' not in rule_codes, (
            f'Nao esperava flag para retention_action="{valid_action}"'
        )


def test_non_retention_categories_skip_retention_inconsistency_rules():
    row = _make_row_data(
        category='CC Informativo',
        retention_action='Nao Retido',
        final_outcome='Resolvido fora de retencao',
    )

    flags = detect_inconsistencies(row)

    assert flags == []
