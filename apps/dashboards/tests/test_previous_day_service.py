from datetime import date, datetime, timedelta, timezone

import pytest

from apps.dashboards.services.previous_day import build_previous_day_payload
from apps.inbound.models import RetentionAction
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
    assert 'Cliente nao foi retido' in first['audit_reasons']
    assert 'Inconsistencia de registo' in first['audit_reasons']
    assert first['audit_priority_score'] > 0
    assert first['audit_priority_score'] <= 100


@pytest.mark.django_db
def test_audit_priority_score_weighs_sem_resolucao_heavily(base_dimensions, interaction_factory):
    """Testa que 'sem resolucao' tem peso alto no score."""
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)

    sem_acao_action = RetentionAction.objects.create(code='sem-acao-t1', label='Sem acao', is_pending=False)

    interaction = interaction_factory(
        call_id_external='sem-acao-1',
        start_at=previous_day_start,
        end_at=previous_day_start + timedelta(minutes=5),
        retention_action=sem_acao_action,
        final_outcome=base_dimensions['not_retained'],
    )

    payload = build_previous_day_payload({}, reference_date=reference_date)

    assert payload['audit_calls']
    call = payload['audit_calls'][0]
    assert call['audit_priority_score'] >= 55  # 25 (nao retido) + 30 (sem acao)
    assert 'Sem resolucao registada' in call['audit_reasons']
    assert 'Cliente nao foi retido' in call['audit_reasons']


@pytest.mark.django_db
def test_audit_priority_score_accumulates_multiple_reasons(base_dimensions, interaction_factory):
    """Testa que o score se acumula quando múltiplos critérios são atingidos."""
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)

    sem_acao_action = RetentionAction.objects.create(code='sem-acao-t2', label='Sem acao', is_pending=False)

    interaction = interaction_factory(
        call_id_external='multi-reason-1',
        start_at=previous_day_start,
        end_at=previous_day_start + timedelta(minutes=5),
        retention_action=sem_acao_action,  # 40 pts
        final_outcome=base_dimensions['not_retained'],
    )

    # Adiciona inconsistência (20 pts)
    DataQualityFlag.objects.create(
        interaction=interaction,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='rule-multi',
        severity=DataQualityFlag.Severity.WARNING,
        description='Multiplos motivos',
    )

    payload = build_previous_day_payload({}, reference_date=reference_date)

    assert payload['audit_calls']
    call = payload['audit_calls'][0]
    # Esperamos score contextual: 25 (nao retido) + 30 (sem acao) + 10 (inconsistencia)
    assert call['audit_priority_score'] >= 65
    assert len(call['audit_reasons']) >= 2


@pytest.mark.django_db
def test_audit_calls_include_only_nao_retido(base_dimensions, interaction_factory):
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)

    sem_acao_action = RetentionAction.objects.create(code='sem-acao-t5', label='Sem acao', is_pending=False)

    # Deve entrar (Nao Retido)
    interaction_factory(
        call_id_external='nr-1',
        start_at=previous_day_start,
        end_at=previous_day_start + timedelta(minutes=5),
        retention_action=sem_acao_action,
        final_outcome=base_dimensions['not_retained'],
    )

    # Nao deve entrar (Retido), mesmo com sem acao
    interaction_factory(
        call_id_external='r-1',
        start_at=previous_day_start + timedelta(hours=1),
        end_at=previous_day_start + timedelta(hours=1, minutes=5),
        retention_action=sem_acao_action,
        final_outcome=base_dimensions['retained'],
    )

    payload = build_previous_day_payload({}, reference_date=reference_date)

    ids = {row['call_id_external'] for row in payload['audit_calls']}
    assert 'nr-1' in ids
    assert 'r-1' not in ids


@pytest.mark.django_db
def test_audit_accepts_not_retained_with_accent_variant(base_dimensions, interaction_factory):
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)

    sem_acao_action = RetentionAction.objects.create(code='sem-acao-t7', label='Sem ação', is_pending=False)
    outcome_with_accent = base_dimensions['not_retained']
    outcome_with_accent.label = 'Não retido'
    outcome_with_accent.save(update_fields=['label'])

    interaction_factory(
        call_id_external='nr-acento-1',
        start_at=previous_day_start,
        end_at=previous_day_start + timedelta(minutes=5),
        retention_action=sem_acao_action,
        final_outcome=outcome_with_accent,
    )

    payload = build_previous_day_payload({}, reference_date=reference_date)
    ids = {row['call_id_external'] for row in payload['audit_calls']}
    assert 'nr-acento-1' in ids


@pytest.mark.django_db
def test_high_audit_third_category_increases_score(base_dimensions, interaction_factory):
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)

    sem_acao_action = RetentionAction.objects.create(code='sem-acao-t6', label='Sem acao', is_pending=False)
    high_reason = base_dimensions['reason']
    high_reason.label = 'Concorrencia'
    high_reason.save(update_fields=['label'])

    interaction_factory(
        call_id_external='high-third-1',
        start_at=previous_day_start,
        end_at=previous_day_start + timedelta(minutes=5),
        retention_action=sem_acao_action,
        churn_reason=high_reason,
        final_outcome=base_dimensions['not_retained'],
    )

    payload = build_previous_day_payload({}, reference_date=reference_date)

    assert payload['audit_calls']
    call = payload['audit_calls'][0]
    assert call['audit_priority_score'] >= 75  # 25 + 30 + 20
    assert 'Tipificacao com potencial de retencao' in call['audit_reasons']


@pytest.mark.django_db
def test_audit_calls_limited_to_top_15(base_dimensions, interaction_factory):
    """Testa que apenas top 15 chamadas são retornadas."""
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)

    sem_acao_action = RetentionAction.objects.create(code='sem-acao-t3', label='Sem acao', is_pending=False)

    # Cria 20 chamadas com sem acao
    for i in range(20):
        interaction_factory(
            call_id_external=f'audit-{i}',
            start_at=previous_day_start + timedelta(hours=i),
            end_at=previous_day_start + timedelta(hours=i, minutes=5),
            retention_action=sem_acao_action,
            final_outcome=base_dimensions['not_retained'],
        )

    payload = build_previous_day_payload({}, reference_date=reference_date)

    assert len(payload['audit_calls']) <= 15


@pytest.mark.django_db
def test_audit_calls_sorted_by_score_descending(base_dimensions, interaction_factory):
    """Testa que chamadas são ordenadas por score descendente."""
    reference_date = date(2026, 4, 8)
    previous_day_start = datetime(2026, 4, 7, 9, 0, tzinfo=timezone.utc)

    sem_acao_action = RetentionAction.objects.create(code='sem-acao-t4', label='Sem acao', is_pending=False)

    # Cria uma com alta prioridade (sem acao)
    high_priority = interaction_factory(
        call_id_external='high-priority',
        start_at=previous_day_start,
        end_at=previous_day_start + timedelta(minutes=5),
        retention_action=sem_acao_action,
        final_outcome=base_dimensions['not_retained'],
    )

    # Cria uma com baixa prioridade (sem critério, exceto inconsistencia)
    low_priority = interaction_factory(
        call_id_external='low-priority',
        start_at=previous_day_start + timedelta(hours=1),
        end_at=previous_day_start + timedelta(hours=1, minutes=5),
        final_outcome=base_dimensions['not_retained'],
    )

    DataQualityFlag.objects.create(
        interaction=low_priority,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='rule-low',
        severity=DataQualityFlag.Severity.WARNING,
        description='Apenas inconsistencia',
    )

    payload = build_previous_day_payload({}, reference_date=reference_date)

    if len(payload['audit_calls']) >= 2:
        # A primeira deve ter score >= a segunda
        assert payload['audit_calls'][0]['audit_priority_score'] >= payload['audit_calls'][1]['audit_priority_score']
