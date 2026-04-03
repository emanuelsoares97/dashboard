from datetime import date, datetime, timedelta, timezone

from apps.quality.models import DataQualityFlag
from apps.dashboards.services import (
    build_dashboard_payload,
    build_churn_reason_table,
    build_monthly_rates_summary,
    build_monthly_rates_table,
    build_retention_action_table,
    build_service_type_table,
    build_temporal_table,
    calculate_general_kpis,
    get_status_class,
    generate_insights,
)
_compute_delta,
from apps.inbound.models import ChurnReason, Interaction, ServiceType


def test_kpis_return_zero_when_queryset_is_empty(db):
    kpis = calculate_general_kpis(Interaction.objects.none())

    assert kpis['total_calls'] == 0
    assert kpis['retention_rate'] == 0.0
    assert kpis['non_retention_rate'] == 0.0
    assert kpis['call_drop_rate'] == 0.0


def test_kpis_calculate_retention_and_zero_division_safely(interaction_factory, base_dimensions):
    interaction_factory(call_id_external='kpi-1', final_outcome=base_dimensions['retained'])
    interaction_factory(call_id_external='kpi-2', final_outcome=base_dimensions['not_retained'])
    interaction_factory(
        call_id_external='kpi-3',
        final_outcome=base_dimensions['not_retained'],
        is_call_drop=True,
    )

    queryset = base_dimensions['agent'].interactions.all()
    kpis = calculate_general_kpis(queryset)

    assert kpis['total_calls'] == 3
    assert kpis['total_retained'] == 1
    assert kpis['total_non_retained'] == 1
    assert kpis['total_call_drop'] == 1
    assert kpis['retention_rate'] == 33.33


def test_build_dashboard_payload_with_assistant_filter(interaction_factory, base_dimensions):
    agent_b = base_dimensions['team'].agents.create(name='Bruno')
    interaction_factory(call_id_external='a-1', agent=base_dimensions['agent'])
    interaction_factory(
        call_id_external='b-1',
        agent=agent_b,
        start_at=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 2, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        granularity='day',
        assistant_name='Ana',
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
    )

    assert payload['general_kpis']['total_calls'] == 1
    assert payload['assistant_ranking_table'][0]['assistant_name'] == 'Ana'
    assert payload['frontend_payload']['temporal_chart']['labels']


def test_build_dashboard_payload_includes_assistant_detail(interaction_factory):
    interaction = interaction_factory(call_id_external='detail-1')

    payload = build_dashboard_payload(assistant_id=interaction.agent_id)

    assert 'assistant_detail' in payload
    assert payload['assistant_detail']['kpis']['total_calls'] >= 1
    assert 'tipification_non_retained' in payload['assistant_detail']


def test_build_temporal_table_fills_previous_month_with_zero_when_no_data(db):
    rows = build_temporal_table(
        Interaction.objects.none(),
        granularity='month',
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    assert len(rows) == 1
    assert rows[0]['period'] == '2026-03-01'
    assert rows[0]['total_calls'] == 0
    assert rows[0]['retention_rate'] == 0.0


def test_generate_insights_returns_empty_for_empty_dataset(db):
    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    assert len(insights) == 1
    assert insights[0]['title'] == 'Insight indisponivel'
    assert insights[0]['value'] == 'Sem dados'


def test_generate_insights_returns_unavailable_when_sample_is_too_small(interaction_factory):
    interaction_factory(call_id_external='small-1')

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    assert len(insights) == 1
    assert insights[0]['title'] == 'Insight indisponivel'
    assert insights[0]['value'] == 'Amostra reduzida'


def test_generate_insights_includes_expected_cards(interaction_factory, base_dimensions):
    agent_b = base_dimensions['team'].agents.create(name='Bruno')
    action_b = base_dimensions['pending_action']

    interaction_factory(call_id_external='ins-1', agent=base_dimensions['agent'])
    interaction_factory(
        call_id_external='ins-2',
        agent=agent_b,
        final_outcome=base_dimensions['not_retained'],
    )
    interaction_factory(call_id_external='ins-3', agent=base_dimensions['agent'])
    interaction_factory(call_id_external='ins-4', agent=agent_b, retention_action=action_b)
    interaction_factory(call_id_external='ins-5', agent=base_dimensions['agent'], retention_action=action_b)

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    titles = {item['title'] for item in insights}
    assert 'Pior motivo de corte' in titles
    assert 'Melhor acao de retencao' in titles
    assert 'Servico com maior nao retencao' in titles
    assert 'Assistente acima da media' in titles
    assert 'Assistente abaixo da media' in titles
    assert 'Total de inconsistencias' in titles


def test_generate_insights_ignores_assistant_below_average_calls(base_dimensions, interaction_factory):
    team = base_dimensions['team']
    strong_agent = team.agents.create(name='Bruno')
    weak_agent = team.agents.create(name='Carla')
    outlier_agent = team.agents.create(name='Diana')

    for idx in range(10):
        interaction_factory(call_id_external=f'strong-{idx}', agent=strong_agent, final_outcome=base_dimensions['retained'])

    for idx in range(10):
        interaction_factory(
            call_id_external=f'weak-{idx}',
            agent=weak_agent,
            final_outcome=base_dimensions['not_retained'],
        )

    interaction_factory(call_id_external='outlier-1', agent=outlier_agent, final_outcome=base_dimensions['retained'])

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    by_title = {item['title']: item['value'] for item in insights}
    assert by_title['Assistente acima da media'] == 'Bruno'
    assert by_title['Assistente abaixo da media'] == 'Carla'


def test_generate_insights_worst_reason_uses_only_reasons_above_average_calls(base_dimensions, interaction_factory):
    rare_reason = ChurnReason.objects.create(code='raro', label='Raro')

    for idx in range(5):
        interaction_factory(call_id_external=f'preco-{idx}', churn_reason=base_dimensions['reason'])

    interaction_factory(
        call_id_external='raro-1',
        churn_reason=rare_reason,
        final_outcome=base_dimensions['not_retained'],
    )

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    by_title = {item['title']: item['value'] for item in insights}
    assert by_title['Pior motivo de corte'] == 'Preco'


def test_generate_insights_includes_operational_volume_and_quality_cards(base_dimensions, interaction_factory):
    agent_b = base_dimensions['team'].agents.create(name='Bruno')

    interaction_factory(call_id_external='vol-1', churn_reason=base_dimensions['reason'])
    interaction_factory(call_id_external='vol-2', churn_reason=base_dimensions['reason'])
    interaction_factory(call_id_external='vol-3', agent=agent_b, retention_action=base_dimensions['pending_action'])
    interaction_factory(call_id_external='vol-4', agent=agent_b)
    interaction_factory(call_id_external='vol-5', agent=base_dimensions['agent'])

    flagged_interaction = interaction_factory(call_id_external='qual-1', agent=agent_b)
    DataQualityFlag.objects.create(
        interaction=flagged_interaction,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='rule-inconsistency',
        severity=DataQualityFlag.Severity.WARNING,
        description='Teste de inconsistencia',
    )

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    by_title = {item['title']: item for item in insights}

    assert by_title['Motivo com maior volume']['value'] == 'Preco'
    assert 'chamadas no periodo analisado' in by_title['Motivo com maior volume']['description']

    assert by_title['Acao mais utilizada']['value'] in {'Oferta', 'Pendente'}
    assert 'Aplicada em' in by_title['Acao mais utilizada']['description']

    assert by_title['Assistente com mais inconsistencias']['value'] == 'Bruno'
    assert 'inconsistencias (' in by_title['Assistente com mais inconsistencias']['description']


def test_get_status_class_thresholds():
    assert get_status_class(35, 30) == 'badge-good'
    assert get_status_class(30, 30) == 'badge-warning'
    assert get_status_class(27.99, 30) == 'badge-critical'


def test_table_rows_include_status_classes(interaction_factory, base_dimensions):
    interaction_factory(call_id_external='tbl-1', final_outcome=base_dimensions['retained'])
    interaction_factory(call_id_external='tbl-2', final_outcome=base_dimensions['not_retained'])

    queryset = Interaction.objects.all()

    churn_rows = build_churn_reason_table(queryset)
    action_rows = build_retention_action_table(queryset)
    service_rows = build_service_type_table(queryset)

    assert churn_rows[0]['retention_status_class'].startswith('badge-')
    assert action_rows[0]['success_status_class'].startswith('badge-')
    assert service_rows[0]['retention_status_class'].startswith('badge-')


def test_build_monthly_rates_table_returns_monthly_totals(interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='m-1',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='m-2',
        start_at=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 2, 10, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['not_retained'],
    )

    rows = build_monthly_rates_table(
        Interaction.objects.all(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 28),
    )

    assert len(rows) == 2
    assert rows[0]['month'] == '2026-01'
    assert rows[0]['total_retained'] == 1
    assert rows[1]['month'] == '2026-02'
    assert rows[1]['total_non_retained'] == 1


def test_build_monthly_rates_summary_returns_best_and_worst_month(interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='s-jan-1',
        start_at=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 5, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='s-feb-1',
        start_at=datetime(2026, 2, 5, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 2, 5, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['not_retained'],
    )

    rows = build_monthly_rates_table(
        Interaction.objects.all(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 28),
    )
    summary = build_monthly_rates_summary(rows)

    assert summary['months_with_data'] == 2
    assert summary['best_month']['month'] == '2026-01'
    assert summary['worst_month']['month'] == '2026-02'


def test_build_dashboard_payload_exposes_ui_state_and_table_states(db):
    payload = build_dashboard_payload(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert payload['ui_state']['has_data'] is False
    assert payload['ui_state']['empty_message']
    assert payload['table_states']['assistants']['has_data'] is False
    assert payload['table_states']['default_empty_message']


def test_build_frontend_payload_marks_charts_without_data(interaction_factory):
    interaction_factory(
        call_id_external='chart-1',
        start_at=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 2, 1, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    chart_states = payload['frontend_payload']['chart_states']
    assert chart_states['outcomes_chart']['has_data'] is False
    assert chart_states['temporal_chart']['has_data'] is False


def test_generate_insights_skips_residual_action_as_best(base_dimensions, interaction_factory):
    weak_action = base_dimensions['pending_action']

    interaction_factory(call_id_external='act-main-1', retention_action=base_dimensions['action'])
    interaction_factory(call_id_external='act-main-2', retention_action=base_dimensions['action'])
    interaction_factory(call_id_external='act-main-3', retention_action=base_dimensions['action'])
    interaction_factory(call_id_external='act-main-4', retention_action=base_dimensions['action'])
    interaction_factory(call_id_external='act-weak-1', retention_action=weak_action)

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    by_title = {item['title']: item for item in insights}
    assert by_title['Melhor acao de retencao']['available'] is True
    assert by_title['Melhor acao de retencao']['value'] == 'Oferta'


def test_generate_insights_marks_worst_reason_unavailable_when_irrelevant_volume(base_dimensions, interaction_factory):
    rare_reason = ChurnReason.objects.create(code='raro2', label='Raro 2')

    interaction_factory(call_id_external='r-main-1', churn_reason=base_dimensions['reason'])
    interaction_factory(call_id_external='r-main-2', churn_reason=base_dimensions['reason'])
    interaction_factory(call_id_external='r-main-3', churn_reason=base_dimensions['reason'])
    interaction_factory(call_id_external='r-main-4', churn_reason=base_dimensions['reason'])
    interaction_factory(call_id_external='r-rare-1', churn_reason=rare_reason)

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    by_title = {item['title']: item for item in insights}
    assert by_title['Pior motivo de corte']['available'] is True
    assert by_title['Pior motivo de corte']['warning'] is True


def test_generate_insights_marks_service_unavailable_without_comparison(base_dimensions, interaction_factory):
    interaction_factory(call_id_external='srv-1', service_type=base_dimensions['service'])
    interaction_factory(call_id_external='srv-2', service_type=base_dimensions['service'])
    interaction_factory(call_id_external='srv-3', service_type=base_dimensions['service'])
    interaction_factory(call_id_external='srv-4', service_type=base_dimensions['service'])
    interaction_factory(call_id_external='srv-5', service_type=base_dimensions['service'])

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    by_title = {item['title']: item for item in insights}
    assert by_title['Servico com maior nao retencao']['available'] is False


def test_comparison_today_uses_yesterday_range(interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='cmp-today-current',
        start_at=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 3, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='cmp-today-prev',
        start_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 2, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['retained'],
    )

    payload = build_dashboard_payload(
        date_preset='today',
        start_date=date(2026, 4, 3),
        end_date=date(2026, 4, 3),
    )

    ctx = payload['comparison_context']
    assert ctx['enabled'] is True
    assert ctx['previous_start'] == date(2026, 4, 2)
    assert ctx['previous_end'] == date(2026, 4, 2)


def test_comparison_last_7_days_uses_previous_7_days(interaction_factory):
    interaction_factory(
        call_id_external='cmp-7-current',
        start_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        date_preset='last_7_days',
        start_date=date(2026, 3, 28),
        end_date=date(2026, 4, 3),
    )

    ctx = payload['comparison_context']
    assert ctx['enabled'] is True
    assert ctx['previous_start'] == date(2026, 3, 21)
    assert ctx['previous_end'] == date(2026, 3, 27)


def test_comparison_current_month_uses_equivalent_days_in_previous_month(interaction_factory):
    interaction_factory(
        call_id_external='cmp-cm-current',
        start_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 2, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        date_preset='current_month',
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 3),
    )

    ctx = payload['comparison_context']
    assert ctx['enabled'] is True
    assert ctx['previous_start'] == date(2026, 3, 1)
    assert ctx['previous_end'] == date(2026, 3, 3)


def test_comparison_previous_month_uses_month_before(interaction_factory):
    interaction_factory(
        call_id_external='cmp-pm-current',
        start_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 2, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        date_preset='previous_month',
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    ctx = payload['comparison_context']
    assert ctx['enabled'] is True
    assert ctx['previous_start'] == date(2026, 2, 1)
    assert ctx['previous_end'] == date(2026, 2, 28)


def test_comparison_custom_uses_same_duration_previous_window(interaction_factory):
    interaction_factory(
        call_id_external='cmp-custom-current',
        start_at=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 15, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 20),
    )

    ctx = payload['comparison_context']
    assert ctx['enabled'] is True
    assert ctx['previous_start'] == date(2025, 12, 30)
    assert ctx['previous_end'] == date(2026, 1, 9)


def test_comparison_custom_month_to_date_uses_same_days_previous_month(interaction_factory):
    interaction_factory(
        call_id_external='cmp-custom-mtd-current',
        start_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 4, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 8),
    )

    ctx = payload['comparison_context']
    assert ctx['enabled'] is True
    assert ctx['previous_start'] == date(2026, 3, 1)
    assert ctx['previous_end'] == date(2026, 3, 8)


def test_comparison_delta_and_direction_are_calculated(interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='cmp-delta-current-1',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='cmp-delta-current-2',
        start_at=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='cmp-delta-prev-1',
        start_at=datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 8, 10, 5, tzinfo=timezone.utc),
        final_outcome=base_dimensions['retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 11),
    )

    total_calls_cmp = payload['comparison_kpis']['total_calls']
    assert total_calls_cmp['current'] == 2.0
    assert total_calls_cmp['previous'] == 1.0
    assert total_calls_cmp['delta'] == 1.0
    assert total_calls_cmp['delta_pct'] == 100.0
    assert total_calls_cmp['direction'] == 'up'


def test_comparison_direction_neutral_when_values_match(interaction_factory):
    interaction_factory(
        call_id_external='cmp-neutral-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )
    interaction_factory(
        call_id_external='cmp-neutral-prev',
        start_at=datetime(2026, 1, 9, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 9, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 10),
    )

    total_calls_cmp = payload['comparison_kpis']['total_calls']
    assert total_calls_cmp['direction'] == 'neutral'


def test_comparison_is_disabled_when_date_range_is_missing(db):
    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=None,
        end_date=None,
    )

    assert payload['comparison_context']['enabled'] is False
    assert payload['comparison_kpis'] == {}


def test_build_dashboard_payload_includes_comparison_data_when_applicable(interaction_factory):
    interaction_factory(
        call_id_external='cmp-payload-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 10),
    )

    assert payload['comparison_context']['enabled'] is True
    assert 'total_calls' in payload['comparison_kpis']


def test_service_type_comparison_table_calculates_values_and_directions(interaction_factory, base_dimensions):
    premium_service = ServiceType.objects.create(code='premium', label='Premium')

    interaction_factory(
        call_id_external='srv-cmp-a-cur-1',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='srv-cmp-a-cur-2',
        start_at=datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 11, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='srv-cmp-a-cur-3',
        start_at=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 10, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
        final_outcome=base_dimensions['not_retained'],
    )
    interaction_factory(
        call_id_external='srv-cmp-b-cur-1',
        start_at=datetime(2026, 1, 11, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 11, 5, tzinfo=timezone.utc),
        service_type=premium_service,
        final_outcome=base_dimensions['retained'],
    )

    interaction_factory(
        call_id_external='srv-cmp-a-prev-1',
        start_at=datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 8, 10, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='srv-cmp-a-prev-2',
        start_at=datetime(2026, 1, 9, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 9, 10, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
        final_outcome=base_dimensions['not_retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 11),
    )

    by_service = {row['service_type']: row for row in payload['service_type_comparison_table']}

    fibra = by_service['Fibra']
    assert fibra['total_calls'] == 3
    assert fibra['total_calls_previous'] == 2.0
    assert fibra['total_calls_delta'] == 1.0
    assert fibra['total_calls_delta_pct'] == 50.0
    assert fibra['total_calls_direction'] == 'up'

    assert fibra['retention_rate'] == 66.67
    assert fibra['retention_rate_previous'] == 50.0
    assert fibra['retention_rate_delta_pp'] == 16.67
    assert fibra['retention_rate_direction'] == 'up'

    assert fibra['non_retention_rate'] == 33.33
    assert fibra['non_retention_rate_previous'] == 50.0
    assert fibra['non_retention_rate_delta_pp'] == -16.67
    assert fibra['non_retention_rate_direction'] == 'down'

    assert fibra['call_drop_rate_delta_pp'] == 0.0
    assert fibra['call_drop_rate_direction'] == 'neutral'


def test_service_type_comparison_table_handles_service_missing_in_previous_period(interaction_factory, base_dimensions):
    premium_service = ServiceType.objects.create(code='solo', label='Solo')

    interaction_factory(
        call_id_external='srv-only-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        service_type=premium_service,
        final_outcome=base_dimensions['retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 10),
    )

    by_service = {row['service_type']: row for row in payload['service_type_comparison_table']}
    solo = by_service['Solo']

    assert solo['total_calls_previous'] == 0.0
    assert solo['total_calls_delta'] == 1.0
    assert solo['total_calls_delta_pct'] is None
    assert solo['total_calls_direction'] == 'up'
    assert solo['retention_rate_previous'] == 0.0
    assert solo['retention_rate_delta_pp'] == 100.0


def test_service_type_comparison_respects_equivalent_days_period_rule(interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='srv-mtd-cur-1',
        start_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, 10, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
    )
    interaction_factory(
        call_id_external='srv-mtd-cur-2',
        start_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 2, 10, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
    )
    interaction_factory(
        call_id_external='srv-mtd-prev-match',
        start_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 2, 10, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
    )
    interaction_factory(
        call_id_external='srv-mtd-prev-outside',
        start_at=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 20, 10, 5, tzinfo=timezone.utc),
        service_type=base_dimensions['service'],
    )

    payload = build_dashboard_payload(
        date_preset='current_month',
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 3),
    )

    by_service = {row['service_type']: row for row in payload['service_type_comparison_table']}
    fibra = by_service['Fibra']

    assert payload['comparison_context']['previous_start'] == date(2026, 3, 1)
    assert payload['comparison_context']['previous_end'] == date(2026, 3, 3)
    assert fibra['total_calls_previous'] == 1.0


def test_churn_reason_comparison_table_calculates_values_and_directions(interaction_factory, base_dimensions):
    other_reason = ChurnReason.objects.create(code='demora', label='Demora')

    interaction_factory(
        call_id_external='churn-cmp-cur-a-1',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='churn-cmp-cur-a-2',
        start_at=datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 11, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='churn-cmp-cur-a-3',
        start_at=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 10, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
        final_outcome=base_dimensions['not_retained'],
    )
    interaction_factory(
        call_id_external='churn-cmp-cur-b-1',
        start_at=datetime(2026, 1, 11, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 11, 5, tzinfo=timezone.utc),
        churn_reason=other_reason,
        final_outcome=base_dimensions['retained'],
    )

    interaction_factory(
        call_id_external='churn-cmp-prev-a-1',
        start_at=datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 8, 10, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='churn-cmp-prev-a-2',
        start_at=datetime(2026, 1, 9, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 9, 10, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
        final_outcome=base_dimensions['not_retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 11),
    )

    by_reason_id = {row['churn_reason_id']: row for row in payload['churn_reason_comparison_table']}
    preco = by_reason_id[base_dimensions['reason'].id]

    assert preco['total_calls'] == 3
    assert preco['total_calls_previous'] == 2.0
    assert preco['total_calls_delta'] == 1.0
    assert preco['total_calls_delta_pct'] == 50.0
    assert preco['total_calls_direction'] == 'up'

    assert preco['retention_rate'] == 66.67
    assert preco['retention_rate_previous'] == 50.0
    assert preco['retention_rate_delta_pp'] == 16.67
    assert preco['retention_rate_direction'] == 'up'

    assert preco['non_retention_rate'] == 33.33
    assert preco['non_retention_rate_previous'] == 50.0
    assert preco['non_retention_rate_delta_pp'] == -16.67
    assert preco['non_retention_rate_direction'] == 'down'

    assert preco['call_drop_rate_delta_pp'] == 0.0
    assert preco['call_drop_rate_direction'] == 'neutral'


def test_churn_reason_comparison_table_handles_reason_missing_in_previous_period(interaction_factory, base_dimensions):
    new_reason = ChurnReason.objects.create(code='novo', label='Novo')

    interaction_factory(
        call_id_external='churn-only-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        churn_reason=new_reason,
        final_outcome=base_dimensions['retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 10),
    )

    by_reason_id = {row['churn_reason_id']: row for row in payload['churn_reason_comparison_table']}
    novo = by_reason_id[new_reason.id]

    assert novo['total_calls_previous'] == 0.0
    assert novo['total_calls_delta'] == 1.0
    assert novo['total_calls_delta_pct'] is None
    assert novo['total_calls_direction'] == 'up'
    assert novo['retention_rate_previous'] == 0.0
    assert novo['retention_rate_delta_pp'] == 100.0


def test_churn_reason_comparison_respects_equivalent_days_period_rule(interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='churn-mtd-cur-1',
        start_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, 10, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
    )
    interaction_factory(
        call_id_external='churn-mtd-cur-2',
        start_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 2, 10, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
    )
    interaction_factory(
        call_id_external='churn-mtd-prev-match',
        start_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 2, 10, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
    )
    interaction_factory(
        call_id_external='churn-mtd-prev-outside',
        start_at=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 20, 10, 5, tzinfo=timezone.utc),
        churn_reason=base_dimensions['reason'],
    )

    payload = build_dashboard_payload(
        date_preset='current_month',
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 3),
    )

    by_reason_id = {row['churn_reason_id']: row for row in payload['churn_reason_comparison_table']}
    reason_row = by_reason_id[base_dimensions['reason'].id]

    assert payload['comparison_context']['previous_start'] == date(2026, 3, 1)
    assert payload['comparison_context']['previous_end'] == date(2026, 3, 3)
    assert reason_row['total_calls_previous'] == 1.0


def test_retention_action_comparison_table_calculates_values_and_directions(interaction_factory, base_dimensions):
    other_action = base_dimensions['pending_action']

    interaction_factory(
        call_id_external='action-cmp-cur-a-1',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='action-cmp-cur-a-2',
        start_at=datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 11, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='action-cmp-cur-a-3',
        start_at=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 10, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
        final_outcome=base_dimensions['not_retained'],
    )
    interaction_factory(
        call_id_external='action-cmp-cur-b-1',
        start_at=datetime(2026, 1, 11, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 11, 5, tzinfo=timezone.utc),
        retention_action=other_action,
        final_outcome=base_dimensions['retained'],
    )

    interaction_factory(
        call_id_external='action-cmp-prev-a-1',
        start_at=datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 8, 10, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='action-cmp-prev-a-2',
        start_at=datetime(2026, 1, 9, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 9, 10, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
        final_outcome=base_dimensions['not_retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 11),
    )

    by_action_id = {row['retention_action_id']: row for row in payload['retention_action_comparison_table']}
    oferta = by_action_id[base_dimensions['action'].id]

    assert oferta['total_used'] == 3
    assert oferta['total_used_previous'] == 2.0
    assert oferta['total_used_delta'] == 1.0
    assert oferta['total_used_delta_pct'] == 50.0
    assert oferta['total_used_direction'] == 'up'

    assert oferta['success_rate'] == 66.67
    assert oferta['success_rate_previous'] == 50.0
    assert oferta['success_rate_delta_pp'] == 16.67
    assert oferta['success_rate_direction'] == 'up'

    assert oferta['failure_rate'] == 33.33
    assert oferta['failure_rate_previous'] == 50.0
    assert oferta['failure_rate_delta_pp'] == -16.67
    assert oferta['failure_rate_direction'] == 'down'


def test_retention_action_comparison_table_handles_action_missing_in_previous_period(interaction_factory, base_dimensions):
    new_action = base_dimensions['team'].retention_actions.create(code='nova', label='Nova')

    interaction_factory(
        call_id_external='action-only-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        retention_action=new_action,
        final_outcome=base_dimensions['retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 10),
    )

    by_action_id = {row['retention_action_id']: row for row in payload['retention_action_comparison_table']}
    nova = by_action_id[new_action.id]

    assert nova['total_used_previous'] == 0.0
    assert nova['total_used_delta'] == 1.0
    assert nova['total_used_delta_pct'] is None
    assert nova['total_used_direction'] == 'up'
    assert nova['success_rate_previous'] == 0.0
    assert nova['success_rate_delta_pp'] == 100.0


def test_retention_action_comparison_respects_equivalent_days_period_rule(interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='action-mtd-cur-1',
        start_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, 10, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
    )
    interaction_factory(
        call_id_external='action-mtd-cur-2',
        start_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 2, 10, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
    )
    interaction_factory(
        call_id_external='action-mtd-prev-match',
        start_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 2, 10, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
    )
    interaction_factory(
        call_id_external='action-mtd-prev-outside',
        start_at=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 20, 10, 5, tzinfo=timezone.utc),
        retention_action=base_dimensions['action'],
    )

    payload = build_dashboard_payload(
        date_preset='current_month',
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 3),
    )

    by_action_id = {row['retention_action_id']: row for row in payload['retention_action_comparison_table']}
    action_row = by_action_id[base_dimensions['action'].id]

    assert payload['comparison_context']['previous_start'] == date(2026, 3, 1)
    assert payload['comparison_context']['previous_end'] == date(2026, 3, 3)
    assert action_row['total_used_previous'] == 1.0


def test_inconsistency_comparison_section_calculates_kpis_and_by_assistant(base_dimensions, interaction_factory):
    agent_b = base_dimensions['team'].agents.create(name='Bruno')

    flagged_current = interaction_factory(
        call_id_external='inc-cmp-cur-a-1',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )
    flagged_current_2 = interaction_factory(
        call_id_external='inc-cmp-cur-a-2',
        start_at=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )
    flagged_current_b = interaction_factory(
        call_id_external='inc-cmp-cur-b-1',
        start_at=datetime(2026, 1, 11, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 11, 5, tzinfo=timezone.utc),
        agent=agent_b,
    )

    flagged_previous = interaction_factory(
        call_id_external='inc-cmp-prev-a-1',
        start_at=datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 8, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )

    DataQualityFlag.objects.create(
        interaction=flagged_current,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='inc-cur-1',
        severity=DataQualityFlag.Severity.WARNING,
        description='Inconsistencia atual 1',
    )
    DataQualityFlag.objects.create(
        interaction=flagged_current_2,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='inc-cur-2',
        severity=DataQualityFlag.Severity.WARNING,
        description='Inconsistencia atual 2',
    )
    DataQualityFlag.objects.create(
        interaction=flagged_current_b,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='inc-cur-3',
        severity=DataQualityFlag.Severity.WARNING,
        description='Inconsistencia atual 3',
    )
    DataQualityFlag.objects.create(
        interaction=flagged_previous,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='inc-prev-1',
        severity=DataQualityFlag.Severity.WARNING,
        description='Inconsistencia anterior',
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 11),
    )

    section = payload['inconsistency_comparison_section']
    assert section['kpis']['total_inconsistencies'] == 3
    assert section['kpis']['total_inconsistencies_previous'] == 1.0
    assert section['kpis']['total_inconsistencies_delta'] == 2.0
    assert section['kpis']['total_inconsistencies_delta_pct'] == 200.0
    assert section['kpis']['total_inconsistencies_direction'] == 'up'

    assert section['kpis']['global_inconsistency_rate'] == 100.0
    assert section['kpis']['global_inconsistency_rate_previous'] == 100.0
    assert section['kpis']['global_inconsistency_rate_delta_pp'] == 0.0
    assert section['kpis']['global_inconsistency_rate_direction'] == 'neutral'

    by_assistant = {row['assistant_id']: row for row in section['kpis']['by_assistant']}
    ana = by_assistant[base_dimensions['agent'].id]
    assert ana['inconsistency_total'] == 2
    assert ana['inconsistency_total_previous'] == 1.0
    assert ana['inconsistency_total_delta'] == 1.0
    assert ana['inconsistency_total_delta_pct'] == 100.0
    assert ana['inconsistency_total_direction'] == 'up'
    assert ana['inconsistency_rate'] == 66.67
    assert ana['inconsistency_rate_previous'] == 100.0
    assert ana['inconsistency_rate_delta_pp'] == -33.33
    assert ana['inconsistency_rate_direction'] == 'down'


def test_inconsistency_comparison_section_handles_assistant_missing_in_previous_period(base_dimensions, interaction_factory):
    new_agent = base_dimensions['team'].agents.create(name='Nova')
    flagged_current = interaction_factory(
        call_id_external='inc-only-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        agent=new_agent,
    )
    DataQualityFlag.objects.create(
        interaction=flagged_current,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        rule_code='inc-only',
        severity=DataQualityFlag.Severity.WARNING,
        description='Inconsistencia nova',
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 10),
    )

    by_assistant = {row['assistant_id']: row for row in payload['inconsistency_comparison_section']['kpis']['by_assistant']}
    nova = by_assistant[new_agent.id]

    assert nova['inconsistency_total_previous'] == 0.0
    assert nova['inconsistency_total_delta'] == 1.0
    assert nova['inconsistency_total_delta_pct'] is None
    assert nova['inconsistency_total_direction'] == 'up'


def test_inconsistency_comparison_respects_equivalent_days_period_rule(base_dimensions, interaction_factory):
    flagged_current = interaction_factory(
        call_id_external='inc-mtd-cur-1',
        start_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )
    flagged_previous = interaction_factory(
        call_id_external='inc-mtd-prev-match',
        start_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 2, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )
    flagged_outside = interaction_factory(
        call_id_external='inc-mtd-prev-outside',
        start_at=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 20, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )

    for interaction, code in ((flagged_current, 'cur'), (flagged_previous, 'prev-match'), (flagged_outside, 'prev-outside')):
        DataQualityFlag.objects.create(
            interaction=interaction,
            flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
            rule_code=f'inc-{code}',
            severity=DataQualityFlag.Severity.WARNING,
            description=f'Inconsistencia {code}',
        )

    payload = build_dashboard_payload(
        date_preset='current_month',
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 3),
    )

    section = payload['inconsistency_comparison_section']
    assert payload['comparison_context']['previous_start'] == date(2026, 3, 1)
    assert payload['comparison_context']['previous_end'] == date(2026, 3, 3)
    assert section['kpis']['total_inconsistencies_previous'] == 1.0


def test_assistant_comparison_table_calculates_values_and_directions(interaction_factory, base_dimensions):
    agent_b = base_dimensions['team'].agents.create(name='Bruno')

    interaction_factory(
        call_id_external='asst-cmp-a-cur-1',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='asst-cmp-a-cur-2',
        start_at=datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 11, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='asst-cmp-a-cur-3',
        start_at=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
        final_outcome=base_dimensions['not_retained'],
    )
    interaction_factory(
        call_id_external='asst-cmp-b-cur-1',
        start_at=datetime(2026, 1, 11, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 11, 11, 5, tzinfo=timezone.utc),
        agent=agent_b,
        final_outcome=base_dimensions['retained'],
    )

    interaction_factory(
        call_id_external='asst-cmp-a-prev-1',
        start_at=datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 8, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='asst-cmp-a-prev-2',
        start_at=datetime(2026, 1, 9, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 9, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
        final_outcome=base_dimensions['not_retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 11),
    )

    by_assistant_id = {row['assistant_id']: row for row in payload['assistant_comparison_table']}

    ana = by_assistant_id[base_dimensions['agent'].id]
    assert ana['total_calls'] == 3
    assert ana['total_calls_previous'] == 2.0
    assert ana['total_calls_delta'] == 1.0
    assert ana['total_calls_delta_pct'] == 50.0
    assert ana['total_calls_direction'] == 'up'

    assert ana['retention_rate'] == 66.67
    assert ana['retention_rate_previous'] == 50.0
    assert ana['retention_rate_delta_pp'] == 16.67
    assert ana['retention_rate_direction'] == 'up'

    assert ana['non_retention_rate'] == 33.33
    assert ana['non_retention_rate_previous'] == 50.0
    assert ana['non_retention_rate_delta_pp'] == -16.67
    assert ana['non_retention_rate_direction'] == 'down'

    assert ana['call_drop_rate_delta_pp'] == 0.0
    assert ana['call_drop_rate_direction'] == 'neutral'

    assert ana['inconsistency_rate_delta_pp'] == 0.0
    assert ana['avg_duration_seconds_delta'] == 0.0


def test_assistant_comparison_table_handles_assistant_missing_in_previous_period(interaction_factory, base_dimensions):
    agent_new = base_dimensions['team'].agents.create(name='Nova')

    interaction_factory(
        call_id_external='asst-only-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
        agent=agent_new,
        final_outcome=base_dimensions['retained'],
    )

    payload = build_dashboard_payload(
        date_preset='custom',
        start_date=date(2026, 1, 10),
        end_date=date(2026, 1, 10),
    )

    by_assistant_id = {row['assistant_id']: row for row in payload['assistant_comparison_table']}
    nova = by_assistant_id[agent_new.id]

    assert nova['total_calls_previous'] == 0.0
    assert nova['total_calls_delta'] == 1.0
    assert nova['total_calls_delta_pct'] is None
    assert nova['total_calls_direction'] == 'up'
    assert nova['retention_rate_previous'] == 0.0
    assert nova['retention_rate_delta_pp'] == 100.0


def test_assistant_comparison_respects_equivalent_days_period_rule(interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='asst-mtd-cur-1',
        start_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )
    interaction_factory(
        call_id_external='asst-mtd-cur-2',
        start_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 2, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )
    interaction_factory(
        call_id_external='asst-mtd-prev-match',
        start_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 2, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )
    interaction_factory(
        call_id_external='asst-mtd-prev-outside',
        start_at=datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 3, 20, 10, 5, tzinfo=timezone.utc),
        agent=base_dimensions['agent'],
    )

    payload = build_dashboard_payload(
        date_preset='current_month',
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 3),
    )

    by_assistant_id = {row['assistant_id']: row for row in payload['assistant_comparison_table']}
    ana = by_assistant_id[base_dimensions['agent'].id]

    assert payload['comparison_context']['previous_start'] == date(2026, 3, 1)
    assert payload['comparison_context']['previous_end'] == date(2026, 3, 3)
    assert ana['total_calls_previous'] == 1.0


def test_trend_tone_retention_rate_up_is_positive():
    """Retencao subindo deve ter trend_tone positivo (up)."""
    delta = _compute_delta(40.0, 35.0, metric_name='retention_rate')
    assert delta['direction'] == 'up'
    assert delta['trend_tone'] == 'up'


def test_trend_tone_retention_rate_down_is_negative():
    """Retencao descendo deve ter trend_tone negativo (down)."""
    delta = _compute_delta(35.0, 40.0, metric_name='retention_rate')
    assert delta['direction'] == 'down'
    assert delta['trend_tone'] == 'down'


def test_trend_tone_non_retention_rate_up_is_negative():
    """Nao-retencao subindo deve ter trend_tone invertido (negativo)."""
    delta = _compute_delta(10.0, 5.0, metric_name='non_retention_rate')
    assert delta['direction'] == 'up'
    assert delta['trend_tone'] == 'down'


def test_trend_tone_non_retention_rate_down_is_positive():
    """Nao-retencao descendo deve ter trend_tone invertido (positivo)."""
    delta = _compute_delta(5.0, 10.0, metric_name='non_retention_rate')
    assert delta['direction'] == 'down'
    assert delta['trend_tone'] == 'up'


def test_trend_tone_call_drop_rate_up_is_negative():
    """Call drop subindo deve ter trend_tone invertido (negativo)."""
    delta = _compute_delta(8.0, 3.0, metric_name='call_drop_rate')
    assert delta['direction'] == 'up'
    assert delta['trend_tone'] == 'down'


def test_trend_tone_call_drop_rate_down_is_positive():
    """Call drop descendo deve ter trend_tone invertido (positivo)."""
    delta = _compute_delta(3.0, 8.0, metric_name='call_drop_rate')
    assert delta['direction'] == 'down'
    assert delta['trend_tone'] == 'up'


def test_trend_tone_inconsistency_rate_up_is_negative():
    """Inconsistencia subindo deve ter trend_tone invertido (negativo)."""
    delta = _compute_delta(15.0, 10.0, metric_name='inconsistency_rate')
    assert delta['direction'] == 'up'
    assert delta['trend_tone'] == 'down'


def test_trend_tone_inconsistency_rate_down_is_positive():
    """Inconsistencia descendo deve ter trend_tone invertido (positivo)."""
    delta = _compute_delta(10.0, 15.0, metric_name='inconsistency_rate')
    assert delta['direction'] == 'down'
    assert delta['trend_tone'] == 'up'


def test_trend_tone_avg_duration_up_is_negative():
    """Duracao media subindo deve ter trend_tone invertido (negativo)."""
    delta = _compute_delta(125.0, 110.0, metric_name='avg_duration_seconds')
    assert delta['direction'] == 'up'
    assert delta['trend_tone'] == 'down'


def test_trend_tone_avg_duration_down_is_positive():
    """Duracao media descendo deve ter trend_tone invertido (positivo)."""
    delta = _compute_delta(110.0, 125.0, metric_name='avg_duration_seconds')
    assert delta['direction'] == 'down'
    assert delta['trend_tone'] == 'up'


def test_trend_tone_total_calls_matches_direction():
    """Total de chamadas: trend_tone sempre = direction (neutro)."""
    delta_up = _compute_delta(150.0, 100.0, metric_name='total_calls')
    assert delta_up['trend_tone'] == delta_up['direction']
    assert delta_up['trend_tone'] == 'up'

    delta_down = _compute_delta(100.0, 150.0, metric_name='total_calls')
    assert delta_down['trend_tone'] == delta_down['direction']
    assert delta_down['trend_tone'] == 'down'

    delta_neutral = _compute_delta(100.0, 100.0, metric_name='total_calls')
    assert delta_neutral['trend_tone'] == 'neutral'


def test_trend_tone_zero_delta_stays_neutral():
    """Delta zero deve ser neutral em todas as metricas."""
    metrics = ['retention_rate', 'non_retention_rate', 'call_drop_rate', 'inconsistency_rate', 'avg_duration_seconds', 'total_calls']
    for metric in metrics:
        delta = _compute_delta(50.0, 50.0, metric_name=metric)
        assert delta['direction'] == 'neutral', f"Falha em {metric}: direction nao neutral"
        assert delta['trend_tone'] == 'neutral', f"Falha em {metric}: trend_tone nao neutral"


def test_trend_tone_backward_compatibility_without_metric_name():
    """Sem metric_name, trend_tone = direction (compatibilidade)."""
    delta = _compute_delta(10.0, 5.0)
    assert delta['trend_tone'] == delta['direction']
    assert delta['trend_tone'] == 'up'
