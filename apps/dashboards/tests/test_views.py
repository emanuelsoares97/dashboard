import pytest
from django.urls import reverse

from apps.inbound.models import Agent, Team


@pytest.mark.django_db
def test_overview_view_returns_200(client):
    response = client.get(reverse('dashboards:overview'))

    assert response.status_code == 200
    assert 'dashboard' in response.context
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
def test_legacy_agents_redirect_keeps_querystring(client):
    response = client.get(reverse('dashboards:agent_dashboard') + '?assistant_name=ana')

    assert response.status_code == 302
    assert 'assistant_name=ana' in response.url
