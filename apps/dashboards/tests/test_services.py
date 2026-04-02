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
from apps.inbound.models import ChurnReason, Interaction


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

    assert insights == []


def test_generate_insights_includes_expected_cards(interaction_factory, base_dimensions):
    agent_b = base_dimensions['team'].agents.create(name='Bruno')

    interaction_factory(call_id_external='ins-1', agent=base_dimensions['agent'])
    interaction_factory(
        call_id_external='ins-2',
        agent=agent_b,
        final_outcome=base_dimensions['not_retained'],
    )

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
