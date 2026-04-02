from datetime import date, datetime, timedelta, timezone

from apps.dashboards.services import build_dashboard_payload, build_temporal_table, calculate_general_kpis
from apps.inbound.models import Interaction


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
