import pytest
import csv
from io import StringIO
from django.urls import reverse
from datetime import datetime, timezone

from apps.inbound.models import Agent, ServiceType, Team


@pytest.mark.django_db
def test_overview_view_returns_200(client):
    response = client.get(reverse('dashboards:overview'))

    assert response.status_code == 200
    assert 'dashboard' in response.context
    assert 'insights' not in response.context
    assert response.context['active_section'] == 'overview'
    assert response.context['period'] == 'day'


@pytest.mark.django_db
def test_assistants_view_returns_200_with_context(client):
    response = client.get(reverse('dashboards:assistants'))

    assert response.status_code == 200
    assert 'rows' in response.context
    assert response.context['active_section'] == 'assistants'


@pytest.mark.django_db
def test_assistant_detail_returns_200(client):
    team = Team.objects.create(name='Equipa Teste')
    agent = Agent.objects.create(team=team, name='Assistente Teste')

    response = client.get(reverse('dashboards:assistant_detail', args=[agent.id]))

    assert response.status_code == 200
    assert response.context['assistant']['id'] == agent.id
    assert 'detail' in response.context


@pytest.mark.django_db
def test_assistant_detail_returns_404_for_unknown_assistant(client):
    response = client.get(reverse('dashboards:assistant_detail', args=[999999]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_legacy_dashboard_routes_redirect(client):
    team_response = client.get(reverse('dashboards:team_dashboard'))
    agent_response = client.get(reverse('dashboards:agent_dashboard'))

    assert team_response.status_code == 302
    assert agent_response.status_code == 302


@pytest.mark.django_db
def test_overview_with_today_preset_sets_dates_in_context(client):
    response = client.get(reverse('dashboards:overview'), {'date_preset': 'today'})

    assert response.status_code == 200
    assert response.context['start_date']
    assert response.context['end_date']
    assert response.context['date_preset'] == 'today'


@pytest.mark.django_db
def test_overview_defaults_to_current_month_when_no_preset_is_sent(client):
    response = client.get(reverse('dashboards:overview'))

    assert response.status_code == 200
    assert response.context['date_preset'] == 'current_month'
    assert response.context['start_date']
    assert response.context['end_date']


@pytest.mark.django_db
def test_overview_with_invalid_period_falls_back_to_day(client):
    response = client.get(reverse('dashboards:overview'), {'period': 'year'})

    assert response.status_code == 200
    assert response.context['period'] == 'day'


@pytest.mark.django_db
def test_legacy_team_redirect_keeps_querystring(client):
    response = client.get(reverse('dashboards:team_dashboard') + '?period=week')

    assert response.status_code == 302
    assert 'period=week' in response.url


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('route_name', 'context_key', 'active_section'),
    [
        ('dashboards:churn_reasons', 'rows', 'churn'),
        ('dashboards:retention_actions', 'rows', 'actions'),
        ('dashboards:services', 'rows', 'services'),
        ('dashboards:inconsistencies', 'section', 'inconsistencies'),
        ('dashboards:insights', 'insights', 'insights'),
        ('dashboards:monthly_rates', 'rows', 'monthly_rates'),
    ],
)
def test_auxiliary_dashboard_pages_with_invalid_date_filters(client, route_name, context_key, active_section):
    response = client.get(
        reverse(route_name),
        {
            'date_preset': 'custom',
            'start_date': 'data-invalida',
            'end_date': 'outra-invalida',
            'assistant_name': 'Nao Existe',
        },
    )

    assert response.status_code == 200
    assert response.context['active_section'] == active_section
    assert context_key in response.context


@pytest.mark.django_db
def test_monthly_rates_view_includes_summary_context(client):
    response = client.get(reverse('dashboards:monthly_rates'))

    assert response.status_code == 200
    assert 'summary' in response.context


@pytest.mark.django_db
def test_monthly_rates_ignores_date_filter_and_keeps_all_months(client, interaction_factory):
    interaction_factory(
        call_id_external='mr-jan',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )
    interaction_factory(
        call_id_external='mr-feb',
        start_at=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 2, 10, 10, 5, tzinfo=timezone.utc),
    )

    response = client.get(
        reverse('dashboards:monthly_rates'),
        {
            'date_preset': 'today',
            'start_date': '2026-02-01',
            'end_date': '2026-02-28',
        },
    )

    assert response.status_code == 200
    months = [row['month'] for row in response.context['rows']]
    assert '2026-01' in months
    assert '2026-02' in months


@pytest.mark.django_db
def test_legacy_agents_redirect_keeps_querystring(client):
    response = client.get(reverse('dashboards:agent_dashboard') + '?assistant_name=ana')

    assert response.status_code == 302
    assert 'assistant_name=ana' in response.url


@pytest.mark.django_db
def test_overview_keeps_new_global_filters_in_navigation_querystring(client, interaction_factory, base_dimensions):
    interaction = interaction_factory(call_id_external='qst-1')

    response = client.get(
        reverse('dashboards:overview'),
        {
            'service_type_id': str(interaction.service_type_id),
            'churn_reason_id': str(interaction.churn_reason_id),
            'retention_action_id': str(interaction.retention_action_id),
            'final_outcome_id': str(interaction.final_outcome_id),
            'date_preset': 'custom',
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
        },
    )

    assert response.status_code == 200
    querystring = response.context['dashboard_querystring']
    assert f"service_type_id={interaction.service_type_id}" in querystring
    assert f"churn_reason_id={interaction.churn_reason_id}" in querystring
    assert f"retention_action_id={interaction.retention_action_id}" in querystring
    assert f"final_outcome_id={interaction.final_outcome_id}" in querystring


@pytest.mark.django_db
def test_overview_filter_options_include_only_dimensions_with_data(client, interaction_factory, base_dimensions):
    # Cria um servico sem interacoes para confirmar que nao aparece nas opcoes.
    ServiceType.objects.create(code='sem-dados', label='Sem Dados')
    interaction = interaction_factory(call_id_external='opt-1')

    response = client.get(
        reverse('dashboards:overview'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
        },
    )

    assert response.status_code == 200
    service_options = response.context['filter_options']['service_types']
    service_ids = {option['id'] for option in service_options}
    assert interaction.service_type_id in service_ids
    assert len(service_ids) == 1


def _read_csv_rows(response):
    decoded = response.content.decode('utf-8')
    reader = csv.reader(StringIO(decoded))
    return list(reader)


@pytest.mark.django_db
@pytest.mark.parametrize(
    'route_name',
    [
        'dashboards:assistants_csv',
        'dashboards:services_csv',
        'dashboards:inconsistencies_csv',
        'dashboards:monthly_rates_csv',
    ],
)
def test_csv_exports_return_attachment_with_csv_content_type(client, route_name):
    response = client.get(reverse(route_name))

    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/csv')
    assert 'attachment;' in response['Content-Disposition']
    assert '.csv' in response['Content-Disposition']


@pytest.mark.django_db
def test_assistants_csv_respects_active_service_filter(client, interaction_factory, base_dimensions):
    team = base_dimensions['team']
    second_agent = team.agents.create(name='Bruno')
    other_service = ServiceType.objects.create(code='movel', label='Movel')

    interaction_factory(call_id_external='exp-a-1', agent=base_dimensions['agent'], service_type=base_dimensions['service'])
    interaction_factory(call_id_external='exp-a-2', agent=second_agent, service_type=other_service)

    response = client.get(
        reverse('dashboards:assistants_csv'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
            'service_type_id': str(base_dimensions['service'].id),
        },
    )

    rows = _read_csv_rows(response)
    body = rows[1:]

    assert response.status_code == 200
    assert 'assistentes_20260101_20260131.csv' in response['Content-Disposition']
    assert len(body) == 1
    assert body[0][0] == 'Ana'


@pytest.mark.django_db
def test_monthly_rates_csv_respects_non_date_filters(client, interaction_factory, base_dimensions):
    other_service = ServiceType.objects.create(code='tv', label='Televisao')
    interaction_factory(
        call_id_external='exp-m-jan',
        service_type=base_dimensions['service'],
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )
    interaction_factory(
        call_id_external='exp-m-feb',
        service_type=other_service,
        start_at=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 2, 10, 10, 5, tzinfo=timezone.utc),
    )

    response = client.get(
        reverse('dashboards:monthly_rates_csv'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
            'service_type_id': str(base_dimensions['service'].id),
        },
    )

    rows = _read_csv_rows(response)
    months = [row[0] for row in rows[1:]]

    assert response.status_code == 200
    assert 'taxas_mensais_20260101_20260131.csv' in response['Content-Disposition']
    assert months == ['2026-01']
