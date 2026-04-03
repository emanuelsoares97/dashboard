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
