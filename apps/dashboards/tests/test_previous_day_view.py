import pytest
from django.urls import reverse
from datetime import date


@pytest.fixture
def client(dashboard_client_factory):
    client, _ = dashboard_client_factory(username='supervisor-prev-day', group_names=['Supervisores'])
    return client


@pytest.fixture
def assistant_client(dashboard_client_factory):
    client, _ = dashboard_client_factory(username='assistant-prev-day', group_names=['Assistentes'])
    return client


@pytest.mark.django_db
def test_previous_day_view_returns_200_and_context(client):
    response = client.get(reverse('dashboards:previous_day'))

    assert response.status_code == 200
    assert response.context['active_section'] == 'previous_day'
    assert 'previous_day' in response.context
    assert 'kpis' in response.context['previous_day']


@pytest.mark.django_db
def test_previous_day_view_forbids_assistant(assistant_client):
    response = assistant_client.get(reverse('dashboards:previous_day'))

    assert response.status_code == 403


@pytest.mark.django_db
def test_previous_day_view_accepts_explicit_day_filter(client):
    response = client.get(
        reverse('dashboards:previous_day'),
        {
            'date_preset': 'custom',
            'start_date': '2026-04-05',
            'end_date': '2026-04-05',
        },
    )

    assert response.status_code == 200
    assert response.context['previous_day']['day'] == date(2026, 4, 5)
