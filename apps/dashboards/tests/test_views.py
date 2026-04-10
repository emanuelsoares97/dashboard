import pytest
import csv
from io import StringIO
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from datetime import datetime, timezone

from apps.inbound.models import Agent, ServiceType, Team
from apps.dashboards.views.helpers import _annotate_mobile_adjusted_metrics


@pytest.fixture
def client(dashboard_client_factory):
    client, _ = dashboard_client_factory(username='supervisor', group_names=['Supervisores'])
    return client


@pytest.fixture
def assistant_client(dashboard_client_factory):
    client, user = dashboard_client_factory(username='assistant-user', group_names=['Assistentes'])
    team = Team.objects.create(name='Equipa Assistente Ligado')
    agent = Agent.objects.create(team=team, name='Assistente Ligado', user=user)
    return client, user, agent


@pytest.fixture
def coordination_client(dashboard_client_factory):
    client, _ = dashboard_client_factory(username='coord-user', group_names=['Coordenacao'])
    return client


@pytest.fixture
def ungrouped_client(dashboard_client_factory):
    client, _ = dashboard_client_factory(username='no-group-user')
    return client


@pytest.fixture
def superuser_client(django_user_model):
    user = django_user_model.objects.create_superuser(
        username='root-dashboard',
        email='root-dashboard@example.com',
        password='testpass123',
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize(
    'route_name',
    [
        'dashboards:overview',
        'dashboards:overview_mobile',
        'dashboards:overview_fixed',
        'dashboards:outbound',
        'dashboards:services',
        'dashboards:assistants',
        'dashboards:monthly_rates',
        'dashboards:daily_rates',
    ],
)
def test_dashboard_redirects_anonymous_user_to_login(route_name):
    response = Client().get(reverse(route_name))

    assert response.status_code == 302
    assert reverse('core:login') in response.url


@pytest.mark.django_db
def test_dashboard_forbids_authenticated_user_without_dashboard_group(ungrouped_client):
    response = ungrouped_client.get(reverse('dashboards:overview'))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize('client_fixture_name', ['client', 'coordination_client'])
@pytest.mark.parametrize(
    'route_name',
    [
        'dashboards:overview',
        'dashboards:overview_mobile',
        'dashboards:overview_fixed',
        'dashboards:outbound',
        'dashboards:churn_reasons',
        'dashboards:retention_actions',
        'dashboards:services',
        'dashboards:assistants',
        'dashboards:monthly_rates',
        'dashboards:daily_rates',
    ],
)
def test_base_pages_allow_all_dashboard_groups(request, client_fixture_name, route_name):
    test_client = request.getfixturevalue(client_fixture_name)

    response = test_client.get(reverse(route_name))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'route_name',
    [
        'dashboards:overview',
        'dashboards:overview_mobile',
        'dashboards:overview_fixed',
        'dashboards:outbound',
        'dashboards:churn_reasons',
        'dashboards:retention_actions',
        'dashboards:services',
        'dashboards:assistants',
        'dashboards:monthly_rates',
        'dashboards:daily_rates',
    ],
)
def test_assistant_is_redirected_to_own_detail_from_other_dashboard_pages(assistant_client, route_name):
    test_client, _, linked_agent = assistant_client

    response = test_client.get(reverse(route_name))

    assert response.status_code == 302
    assert response.url == reverse('dashboards:assistant_detail', args=[linked_agent.id])


@pytest.mark.django_db
@pytest.mark.parametrize('client_fixture_name', ['client', 'coordination_client'])
def test_assistant_detail_allows_all_dashboard_groups(request, client_fixture_name):
    test_client = request.getfixturevalue(client_fixture_name)
    team = Team.objects.create(name='Equipa Permissoes')
    agent = Agent.objects.create(team=team, name='Assistente Permissoes')

    response = test_client.get(reverse('dashboards:assistant_detail', args=[agent.id]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_assistant_can_access_only_own_detail(assistant_client):
    test_client, _, linked_agent = assistant_client

    response = test_client.get(reverse('dashboards:assistant_detail', args=[linked_agent.id]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_assistant_cannot_access_other_assistant_detail(assistant_client):
    test_client, _, linked_agent = assistant_client
    other_team = Team.objects.create(name='Equipa Outro Assistente')
    other_agent = Agent.objects.create(team=other_team, name='Outro Assistente')

    assert other_agent.id != linked_agent.id

    response = test_client.get(reverse('dashboards:assistant_detail', args=[other_agent.id]))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize('route_name', ['dashboards:inconsistencies', 'dashboards:insights', 'dashboards:previous_day'])
def test_sensitive_pages_forbid_assistants(assistant_client, route_name):
    test_client, _, linked_agent = assistant_client
    response = test_client.get(reverse(route_name))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize('client_fixture_name', ['client', 'coordination_client'])
@pytest.mark.parametrize('route_name', ['dashboards:inconsistencies', 'dashboards:insights', 'dashboards:previous_day'])
def test_sensitive_pages_allow_supervisors_and_coordination(request, client_fixture_name, route_name):
    test_client = request.getfixturevalue(client_fixture_name)

    response = test_client.get(reverse(route_name))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('route_name', ['dashboards:inconsistencies', 'dashboards:insights', 'dashboards:previous_day'])
def test_sensitive_pages_allow_superuser(superuser_client, route_name):
    response = superuser_client.get(reverse(route_name))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'route_name',
    [
        'dashboards:assistants_csv',
        'dashboards:services_csv',
        'dashboards:inconsistencies_csv',
        'dashboards:monthly_rates_csv',
        'dashboards:daily_rates_csv',
    ],
)
def test_csv_exports_forbid_assistants(assistant_client, route_name):
    test_client, _, _ = assistant_client
    response = test_client.get(reverse(route_name))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize('client_fixture_name', ['client', 'coordination_client'])
@pytest.mark.parametrize(
    'route_name',
    [
        'dashboards:assistants_csv',
        'dashboards:services_csv',
        'dashboards:inconsistencies_csv',
        'dashboards:monthly_rates_csv',
        'dashboards:daily_rates_csv',
    ],
)
def test_csv_exports_allow_supervisors_and_coordination(request, client_fixture_name, route_name):
    test_client = request.getfixturevalue(client_fixture_name)

    response = test_client.get(reverse(route_name))

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'route_name',
    [
        'dashboards:assistants_csv',
        'dashboards:services_csv',
        'dashboards:inconsistencies_csv',
        'dashboards:monthly_rates_csv',
        'dashboards:daily_rates_csv',
    ],
)
def test_csv_exports_allow_superuser(superuser_client, route_name):
    response = superuser_client.get(reverse(route_name))

    assert response.status_code == 200


@pytest.mark.django_db
def test_forbidden_dashboard_page_shows_friendly_access_denied_message(assistant_client):
    test_client, _, linked_agent = assistant_client
    response = test_client.get(reverse('dashboards:insights'))

    assert response.status_code == 403
    assert 'Acesso negado' in response.content.decode('utf-8')


@pytest.mark.django_db
def test_overview_view_returns_200(client):
    response = client.get(reverse('dashboards:overview'))

    assert response.status_code == 200
    assert 'dashboard' in response.context
    assert 'insights' not in response.context
    assert response.context['active_section'] == 'overview'
    assert response.context['period'] == 'day'


@pytest.mark.django_db
def test_outbound_view_separates_cc_ret_outbound_from_other_tabs(client, interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='in-1',
        subcategory='CC RET Fibra',
        final_outcome=base_dimensions['retained'],
    )
    interaction_factory(
        call_id_external='out-1',
        subcategory='CC RET Outbound',
        final_outcome=base_dimensions['not_retained'],
    )

    query_params = {
        'date_preset': 'custom',
        'start_date': '2026-01-01',
        'end_date': '2026-01-31',
    }

    overview_response = client.get(reverse('dashboards:overview'), query_params)
    outbound_response = client.get(reverse('dashboards:outbound'), query_params)

    assert overview_response.status_code == 200
    assert outbound_response.status_code == 200
    assert overview_response.context['dashboard']['general_kpis']['total_calls'] == 1
    assert outbound_response.context['dashboard']['general_kpis']['total_calls'] == 1
    assert outbound_response.context['active_section'] == 'outbound'


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
        ('dashboards:previous_day', 'previous_day', 'previous_day'),
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


@pytest.mark.django_db
def test_overview_context_marks_empty_state_when_no_data(client):
    response = client.get(
        reverse('dashboards:overview'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['ui_state']['has_data'] is False
    assert response.context['dashboard']['ui_state']['empty_message']


@pytest.mark.django_db
def test_overview_context_marks_low_sample_warning(client, interaction_factory):
    interaction_factory(
        call_id_external='low-1',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )

    response = client.get(
        reverse('dashboards:overview'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['ui_state']['has_data'] is True
    assert response.context['dashboard']['ui_state']['is_low_sample'] is True


@pytest.mark.django_db
def test_overview_context_includes_comparison_blocks(client, interaction_factory):
    interaction_factory(
        call_id_external='view-cmp-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )

    response = client.get(
        reverse('dashboards:overview'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-10',
            'end_date': '2026-01-10',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['comparison_context']['enabled'] is True
    assert 'total_calls' in response.context['dashboard']['comparison_kpis']


@pytest.mark.django_db
def test_services_context_includes_comparison_rows(client, interaction_factory):
    interaction_factory(
        call_id_external='view-svc-cmp-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )

    response = client.get(
        reverse('dashboards:services'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-10',
            'end_date': '2026-01-10',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['comparison_context']['enabled'] is True
    assert response.context['rows']
    assert 'total_calls_delta' in response.context['rows'][0]


@pytest.mark.django_db
def test_assistants_context_includes_comparison_rows(client, interaction_factory):
    interaction_factory(
        call_id_external='view-asst-cmp-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )

    response = client.get(
        reverse('dashboards:assistants'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-10',
            'end_date': '2026-01-10',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['comparison_context']['enabled'] is True
    assert response.context['rows']
    assert 'total_calls_delta' in response.context['rows'][0]
    assert 'retention_rate_delta_pp' in response.context['rows'][0]
    assert 'avg_duration_seconds_delta' in response.context['rows'][0]


@pytest.mark.django_db
def test_churn_reasons_context_includes_comparison_rows(client, interaction_factory):
    interaction_factory(
        call_id_external='view-churn-cmp-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )

    response = client.get(
        reverse('dashboards:churn_reasons'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-10',
            'end_date': '2026-01-10',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['comparison_context']['enabled'] is True
    assert response.context['rows']
    assert 'total_calls_delta' in response.context['rows'][0]
    assert 'retention_rate_delta_pp' in response.context['rows'][0]


@pytest.mark.django_db
def test_retention_actions_context_includes_comparison_rows(client, interaction_factory):
    interaction_factory(
        call_id_external='view-action-cmp-current',
        start_at=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 10, 5, tzinfo=timezone.utc),
    )

    response = client.get(
        reverse('dashboards:retention_actions'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-10',
            'end_date': '2026-01-10',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['comparison_context']['enabled'] is True
    assert response.context['rows']
    assert 'total_used_delta' in response.context['rows'][0]
    assert 'success_rate_delta_pp' in response.context['rows'][0]


@pytest.mark.django_db
def test_inconsistencies_context_includes_comparison_section(client, interaction_factory):
    response = client.get(
        reverse('dashboards:inconsistencies'),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-10',
            'end_date': '2026-01-10',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['comparison_context']['enabled'] is True
    assert 'total_inconsistencies_previous' in response.context['section']['kpis']
    assert 'global_inconsistency_rate_delta_pp' in response.context['section']['kpis']


@pytest.mark.django_db
def test_assistant_detail_context_includes_comparison_kpis(client, interaction_factory, base_dimensions):
    interaction_factory(
        call_id_external='det-view-1',
        agent=base_dimensions['agent'],
        final_outcome=base_dimensions['retained'],
    )

    response = client.get(
        reverse('dashboards:assistant_detail', args=[base_dimensions['agent'].id]),
        {
            'date_preset': 'custom',
            'start_date': '2026-01-10',
            'end_date': '2026-01-10',
        },
    )

    assert response.status_code == 200
    assert response.context['dashboard']['comparison_context']['enabled'] is True
    detail = response.context['detail']
    assert 'total_calls_previous' in detail['kpis']
    assert 'retention_rate_delta_pp' in detail['kpis']
    assert 'avg_duration_seconds_previous' in detail['kpis']
    assert 'typing_analysis' in detail
    assert 'kpis' in detail['typing_analysis']


# ---------------------------------------------------------------------------
# Unit tests: _annotate_mobile_adjusted_metrics (taxa movel sem pre pago PF)
# ---------------------------------------------------------------------------

def _make_action_row(action, used, retained):
    non_retained = max(used - retained, 0)
    return {
        'retention_action': action,
        'total_used': used,
        'total_retained': retained,
        'total_non_retained': non_retained,
        'success_rate': round((retained / used) * 100, 2) if used else 0.0,
    }


def test_prepago_calls_counted_in_denominator_but_not_as_retained():
    """Chamadas 'Retido Migracao Pre Pago' devem entrar no total (denominador) da
    taxa ajustada mas NAO devem ser contadas como retidas (numerador).

    Cenario:
      - 60 chamadas normais, 40 retidas  → taxa normal = 66.67%
      - 40 chamadas pre-pago, 40 'retidas' (mas excluidas do ajuste)
      - general_kpis: total_calls=100, total_retained=80 → taxa geral = 80%
      - Taxa ajustada = (80 - 40) / 100 = 40.0%

    Se o denominador fosse so as chamadas normais (60), o resultado seria
    40/60 = 66.67% — o teste rejeitaria esse valor.
    """
    payload = {
        'retention_action_table': [
            _make_action_row('Desconto aplicado', used=60, retained=40),
            _make_action_row('Retido Migracao Pre Pago', used=40, retained=40),
        ],
        'general_kpis': {'total_calls': 100, 'total_retained': 80, 'retention_rate': 80.0},
    }

    result = _annotate_mobile_adjusted_metrics(payload)

    adjusted_global = result['general_kpis']['retention_rate_adjusted_mobile']
    assert adjusted_global == 40.0, (
        f"Esperado 40.0% (pre-pago no denominador, nao no numerador) mas obteve {adjusted_global}%"
    )
    assert adjusted_global <= result['general_kpis']['retention_rate']


def test_prepago_row_has_zero_adjusted_retained_and_zero_adjusted_rate():
    """A linha 'Retido Migracao Pre Pago' deve ter adjusted_total_retained=0 e
    adjusted_success_rate=0.0 para indicar que nao conta como retencao real.
    """
    payload = {
        'retention_action_table': [
            _make_action_row('Retido Migracao Pre Pago', used=25, retained=25),
        ],
    }

    result = _annotate_mobile_adjusted_metrics(payload)
    row = result['retention_action_table'][0]

    assert row['adjusted_total_retained'] == 0
    assert row['adjusted_success_rate'] == 0.0


def test_non_prepago_rows_keep_original_retained_count():
    """Linhas de accoes normais (nao pre-pago) nao devem ser alteradas pelo ajuste."""
    payload = {
        'retention_action_table': [
            _make_action_row('Desconto aplicado', used=100, retained=70),
        ],
    }

    result = _annotate_mobile_adjusted_metrics(payload)
    row = result['retention_action_table'][0]

    assert row['adjusted_total_retained'] == 70
    assert row['adjusted_success_rate'] == 70.0


def test_prepago_matching_is_case_insensitive():
    """A comparacao do label de pre-pago deve ser insensivel a maiusculas/minusculas."""
    payload = {
        'retention_action_table': [
            _make_action_row('RETIDO MIGRACAO PRE PAGO', used=10, retained=10),
            _make_action_row('retido migracao pre pago', used=10, retained=10),
            _make_action_row('Retido Migracao Pre Pago', used=10, retained=10),
        ],
    }

    result = _annotate_mobile_adjusted_metrics(payload)

    for row in result['retention_action_table']:
        assert row['adjusted_total_retained'] == 0
        assert row['adjusted_success_rate'] == 0.0
    assert result['general_kpis']['retention_rate_adjusted_mobile'] == 0.0


def test_adjusted_global_rate_zero_when_no_table_rows():
    """Payload sem linhas na tabela deve produzir taxa ajustada 0.0 sem erros."""
    payload = {'retention_action_table': []}

    result = _annotate_mobile_adjusted_metrics(payload)

    assert result['general_kpis']['retention_rate_adjusted_mobile'] == 0.0


def test_mixed_scenario_global_adjusted_rate():
    """Cenario misto: pre-pago + normais + sem accao.

    - 50 chamadas normais, 30 retidas
    - 20 chamadas pre-pago, 20 'retidas'
    - 30 chamadas sem accao, 0 retidas
    general_kpis: total_calls=100, total_retained=50
    Taxa ajustada = (50 - 20) / 100 = 30.0%
    """
    payload = {
        'retention_action_table': [
            _make_action_row('Desconto aplicado', used=50, retained=30),
            _make_action_row('Retido Migracao Pre Pago', used=20, retained=20),
            _make_action_row('Sem acao', used=30, retained=0),
        ],
        'general_kpis': {'total_calls': 100, 'total_retained': 50, 'retention_rate': 50.0},
    }

    result = _annotate_mobile_adjusted_metrics(payload)

    adjusted = result['general_kpis']['retention_rate_adjusted_mobile']
    assert adjusted == 30.0
    assert adjusted <= result['general_kpis']['retention_rate']


def test_adjusted_rate_uses_general_kpis_not_table_sum():
    """Regresso: a taxa ajustada usa general_kpis.total_calls como denominador,
    NAO a soma de total_used da retention_action_table.

    O problema ocorre porque build_retention_action_table aplica
    _exclude_outcome_labels() internamente, excluindo chamadas com retention_action
    igual a labels de OutcomeFinal (ex: 'Nao Retido'). Essas chamadas ficam fora
    da tabela mas existem em general_kpis.total_calls.

    Cenario:
      - 200 chamadas excluidas da tabela (retention_action='Nao Retido'), 0 retidas
      - 200 chamadas normais (na tabela), 190 retidas
      - 100 chamadas pre-pago (na tabela), 100 retidas
      - general_kpis: total_calls=500, total_retained=290 → taxa geral = 58%

    Com denominador ERRADO (soma da tabela = 300):
      (290 - 100) / 300 = 190/300 = 63.33%  > 58%  [BUG: ajustada > geral]

    Com denominador CORRETO (general_kpis.total_calls = 500):
      (290 - 100) / 500 = 190/500 = 38.0%   < 58%  [CORRETO]
    """
    payload = {
        'retention_action_table': [
            # Apenas 300 das 500 chamadas aparecem na tabela
            _make_action_row('Desconto aplicado', used=200, retained=190),
            _make_action_row('Retido Migracao Pre Pago', used=100, retained=100),
        ],
        'general_kpis': {
            'total_calls': 500,
            'total_retained': 290,
            'retention_rate': 58.0,
        },
    }

    result = _annotate_mobile_adjusted_metrics(payload)
    adjusted = result['general_kpis']['retention_rate_adjusted_mobile']

    assert adjusted == 38.0, (
        f"Esperado 38.0% com denominador correto (500), obteve {adjusted}%. "
        "Se o valor fosse 63.33%, o denominador esta a usar a soma da tabela (300) em vez de total_calls (500)."
    )
    assert adjusted <= result['general_kpis']['retention_rate'], (
        "A taxa sem pre-pago nunca pode ser maior do que a taxa geral."
    )
