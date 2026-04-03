from datetime import date, datetime, timezone

from apps.dashboards import selectors
from apps.inbound.models import ChurnReason, OutcomeFinal, RetentionAction, ServiceType


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


def test_selector_filters_by_service(interaction_factory, base_dimensions):
    alt_service = ServiceType.objects.create(code='movel', label='Movel')
    interaction_factory(call_id_external='svc-1', service_type=base_dimensions['service'])
    interaction_factory(call_id_external='svc-2', service_type=alt_service)

    queryset = selectors.get_inbound_queryset()
    filtered = selectors.apply_filters(queryset, service_type_id=alt_service.id)

    assert filtered.count() == 1
    assert filtered.first().service_type_id == alt_service.id


def test_selector_filters_by_churn_reason(interaction_factory, base_dimensions):
    alt_reason = ChurnReason.objects.create(code='qualidade', label='Qualidade')
    interaction_factory(call_id_external='rsn-1', churn_reason=base_dimensions['reason'])
    interaction_factory(call_id_external='rsn-2', churn_reason=alt_reason)

    queryset = selectors.get_inbound_queryset()
    filtered = selectors.apply_filters(queryset, churn_reason_id=alt_reason.id)

    assert filtered.count() == 1
    assert filtered.first().churn_reason_id == alt_reason.id


def test_selector_filters_by_retention_action(interaction_factory, base_dimensions):
    alt_action = RetentionAction.objects.create(code='negociacao', label='Negociacao')
    interaction_factory(call_id_external='act-1', retention_action=base_dimensions['action'])
    interaction_factory(call_id_external='act-2', retention_action=alt_action)

    queryset = selectors.get_inbound_queryset()
    filtered = selectors.apply_filters(queryset, retention_action_id=alt_action.id)

    assert filtered.count() == 1
    assert filtered.first().retention_action_id == alt_action.id


def test_selector_filters_by_final_outcome(interaction_factory, base_dimensions):
    alt_outcome = OutcomeFinal.objects.create(code='cancelado', label='Cancelado')
    interaction_factory(call_id_external='out-1', final_outcome=base_dimensions['retained'])
    interaction_factory(call_id_external='out-2', final_outcome=alt_outcome)

    queryset = selectors.get_inbound_queryset()
    filtered = selectors.apply_filters(queryset, final_outcome_id=alt_outcome.id)

    assert filtered.count() == 1
    assert filtered.first().final_outcome_id == alt_outcome.id


def test_selector_combines_service_filter_with_date_range(interaction_factory, base_dimensions):
    alt_service = ServiceType.objects.create(code='tv', label='Televisao')
    interaction_factory(
        call_id_external='cmb-1',
        service_type=base_dimensions['service'],
        start_at=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 5, 10, 5, tzinfo=timezone.utc),
    )
    interaction_factory(
        call_id_external='cmb-2',
        service_type=alt_service,
        start_at=datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 20, 10, 5, tzinfo=timezone.utc),
    )
    interaction_factory(
        call_id_external='cmb-3',
        service_type=alt_service,
        start_at=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 2, 2, 10, 5, tzinfo=timezone.utc),
    )

    queryset = selectors.get_inbound_queryset()
    filtered = selectors.apply_filters(
        queryset,
        service_type_id=alt_service.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert filtered.count() == 1
    assert filtered.first().call_id_external == 'cmb-2'
