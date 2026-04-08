from datetime import date

import pytest

from apps.dashboards.services import generate_insights
from apps.inbound.models import ChurnReason, ServiceType


@pytest.mark.django_db
def test_generate_insights_enriches_negative_cards_with_operational_guidance(base_dimensions, interaction_factory):
    team = base_dimensions['team']
    agent_b = team.agents.create(name='Bruno')
    other_service = ServiceType.objects.create(code='movel', label='Movel')

    reason_low = ChurnReason.objects.create(code='fatura', label='Fatura')

    for idx in range(5):
        interaction_factory(
            call_id_external=f'ana-ret-{idx}',
            agent=base_dimensions['agent'],
            final_outcome=base_dimensions['retained'],
            service_type=base_dimensions['service'],
            churn_reason=base_dimensions['reason'],
        )

    for idx in range(5):
        interaction_factory(
            call_id_external=f'bru-nret-{idx}',
            agent=agent_b,
            final_outcome=base_dimensions['not_retained'],
            service_type=other_service,
            churn_reason=reason_low,
        )

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    by_title = {item['title']: item for item in insights}

    target_titles = {
        'Assistente abaixo da media',
        'Servico com maior nao retencao',
        'Total de inconsistencias',
        'Motivo com menor taxa de retencao',
    }

    for title in target_titles:
        assert title in by_title
        assert by_title[title]['summary']
        assert by_title[title]['operational_interpretation']
        assert by_title[title]['suggested_actions']
        assert by_title[title]['audit_recommendation']


@pytest.mark.django_db
def test_generate_insights_motivo_nao_indicado_includes_specific_operational_recommendations(
    base_dimensions, interaction_factory
):
    reason_not_indicated = ChurnReason.objects.create(code='motivo-nao-indicado', label='Motivo Nao Indicado')

    for idx in range(5):
        interaction_factory(
            call_id_external=f'nao-indicado-{idx}',
            churn_reason=reason_not_indicated,
            final_outcome=base_dimensions['not_retained'],
        )

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    target = next(item for item in insights if item['title'] == 'Uso de Motivo Nao Indicado')
    assert target['available'] is True
    assert target['operational_interpretation']
    assert target['suggested_actions']
    assert target['audit_recommendation']
