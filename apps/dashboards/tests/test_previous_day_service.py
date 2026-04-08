from datetime import date, datetime, timedelta, timezone

import pytest

from apps.dashboards.services.previous_day import build_previous_day_payload
from apps.quality.models import DataQualityFlag


@pytest.mark.django_db
def test_build_previous_day_payload_returns_expected_sections(base_dimensions, interaction_factory):
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 10, 0, tzinfo=timezone.utc)

    # Dados do dia anterior
    i1 = interaction_factory(
        call_id_external='pd-1',
        start_at=previous_day_start,
        end_at=previous_day_start + timedelta(minutes=4),
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='pd-2',
        start_at=previous_day_start + timedelta(hours=1),
        end_at=previous_day_start + timedelta(hours=1, minutes=5),
        final_outcome=base_dimensions['not_retained'],
        retention_action=base_dimensions['pending_action'],
    )

    DataQualityFlag.objects.create(
        interaction=i1,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='rule-prev-day',
        severity=DataQualityFlag.Severity.WARNING,
        description='Inconsistencia para teste',
    )

    # Dado fora do dia anterior (nao deve entrar)
    interaction_factory(
        call_id_external='pd-outside',
        start_at=datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 6, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_previous_day_payload({}, reference_date=reference_date)

    assert payload['day'] == date(2026, 4, 7)
    assert payload['kpis']['total_calls'] == 2
    assert 'no_action_pct' in payload['kpis']
    assert 'inconsistency_rate' in payload['kpis']
    assert 'top' in payload['assistants']
    assert 'bottom' in payload['assistants']
    assert 'best' in payload['tipification']
    assert 'worst' in payload['tipification']
    assert 'most_used' in payload['actions']
    assert 'highest_success' in payload['actions']
    assert 'lowest_success' in payload['actions']
    assert 'insights' in payload
    assert 'audit_calls' in payload


@pytest.mark.django_db
def test_build_previous_day_payload_prioritizes_audit_calls(base_dimensions, interaction_factory):
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)

    interaction = interaction_factory(
        call_id_external='audit-1',
        start_at=previous_day_start,
        end_at=previous_day_start + timedelta(minutes=6),
        final_outcome=base_dimensions['not_retained'],
        retention_action=base_dimensions['pending_action'],
    )

    DataQualityFlag.objects.create(
        interaction=interaction,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='rule-audit',
        severity=DataQualityFlag.Severity.WARNING,
        description='Inconsistencia para auditoria',
    )

    payload = build_previous_day_payload({}, reference_date=reference_date)

    assert payload['audit_calls']
    first = payload['audit_calls'][0]
    assert first['call_id_external'] == 'audit-1'
    assert 'Chamada sem acao registada' in first['priority_reasons']
    assert 'Inconsistencia de registo' in first['priority_reasons']
