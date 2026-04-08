import pytest
from django.urls import reverse


@pytest.fixture
def client(dashboard_client_factory):
    client, _ = dashboard_client_factory(username='supervisor-insights', group_names=['Supervisores'])
    return client


@pytest.mark.django_db
def test_insights_context_includes_operational_guidance_fields(client, interaction_factory):
    interaction_factory(call_id_external='insight-guidance-1')
    interaction_factory(call_id_external='insight-guidance-2')
    interaction_factory(call_id_external='insight-guidance-3')
    interaction_factory(call_id_external='insight-guidance-4')
    interaction_factory(call_id_external='insight-guidance-5')

    response = client.get(reverse('dashboards:insights'))

    assert response.status_code == 200
    assert response.context['insights']

    sample = response.context['insights'][0]
    assert 'summary' in sample
    assert 'operational_interpretation' in sample
    assert 'suggested_actions' in sample
    assert 'audit_recommendation' in sample
    assert 'insight_total_count' in response.context
    assert 'insight_attention_count' in response.context
    assert 'insight_visible_count' in response.context


@pytest.mark.django_db
def test_insights_mode_attention_filters_to_operational_attention_only(client, interaction_factory):
    interaction_factory(call_id_external='insight-attn-1')
    interaction_factory(call_id_external='insight-attn-2')
    interaction_factory(call_id_external='insight-attn-3')
    interaction_factory(call_id_external='insight-attn-4')
    interaction_factory(call_id_external='insight-attn-5')

    response = client.get(
        reverse('dashboards:insights'),
        {
            'insight_mode': 'attention',
            'date_preset': 'custom',
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        },
    )

    assert response.status_code == 200
    assert response.context['insight_mode'] == 'attention'
    assert response.context['insights']
    assert response.context['insight_visible_count'] == len(response.context['insights'])
    assert response.context['insight_attention_count'] >= response.context['insight_visible_count']
    assert all(
        item.get('suggested_actions') or item.get('audit_recommendation')
        for item in response.context['insights']
    )


@pytest.mark.django_db
def test_insights_mode_invalid_falls_back_to_all(client, interaction_factory):
    interaction_factory(call_id_external='insight-mode-invalid-1')
    interaction_factory(call_id_external='insight-mode-invalid-2')
    interaction_factory(call_id_external='insight-mode-invalid-3')
    interaction_factory(call_id_external='insight-mode-invalid-4')
    interaction_factory(call_id_external='insight-mode-invalid-5')

    response = client.get(reverse('dashboards:insights'), {'insight_mode': 'foo'})

    assert response.status_code == 200
    assert response.context['insight_mode'] == 'all'
