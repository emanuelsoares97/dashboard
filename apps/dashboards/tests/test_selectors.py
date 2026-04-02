from datetime import date, datetime, timezone

from apps.dashboards import selectors


def test_selector_filters_by_date(interaction_factory):
    interaction_factory(
        call_id_external='d-1',
        start_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc),
    )
    interaction_factory(
        call_id_external='d-2',
        start_at=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 2, 1, 10, 5, tzinfo=timezone.utc),
    )

    queryset = selectors.get_inbound_queryset()
    filtered = selectors.apply_filters(
        queryset,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 10),
    )

    assert filtered.count() == 1
    assert filtered.first().call_id_external == 'd-2'


def test_selector_filters_by_assistant_name(interaction_factory, base_dimensions):
    team = base_dimensions['team']
    other_agent = team.agents.create(name='Carlos')

    interaction_factory(call_id_external='n-1', agent=base_dimensions['agent'])
    interaction_factory(call_id_external='n-2', agent=other_agent)

    queryset = selectors.get_inbound_queryset()
    filtered = selectors.apply_filters(queryset, assistant_name='ana')

    assert filtered.count() == 1
    assert filtered.first().agent.name == 'Ana'
