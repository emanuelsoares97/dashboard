import pytest
from django.urls import reverse

from apps.inbound.models import Agent, Team


@pytest.mark.django_db
def test_overview_view_returns_200(client):
    response = client.get(reverse('dashboards:overview'))

    assert response.status_code == 200
    assert 'dashboard' in response.context
    assert response.context['active_section'] == 'overview'


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
def test_legacy_dashboard_routes_redirect(client):
    team_response = client.get(reverse('dashboards:team_dashboard'))
    agent_response = client.get(reverse('dashboards:agent_dashboard'))

    assert team_response.status_code == 302
    assert agent_response.status_code == 302
