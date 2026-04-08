from datetime import date

import pytest

from apps.dashboards.services import generate_insights
from apps.inbound.models import ServiceType


@pytest.mark.django_db
def test_generate_insights_enriches_negative_cards_with_operational_guidance(base_dimensions, interaction_factory):
    team = base_dimensions['team']
    agent_b = team.agents.create(name='Bruno')
    other_service = ServiceType.objects.create(code='movel', label='Movel')

    for idx in range(3):
        interaction_factory(
            call_id_external=f'ana-ret-{idx}',
            agent=base_dimensions['agent'],
            final_outcome=base_dimensions['retained'],
            service_type=base_dimensions['service'],
        )

    for idx in range(3):
        interaction_factory(
            call_id_external=f'bru-nret-{idx}',
            agent=agent_b,
            final_outcome=base_dimensions['not_retained'],
            retention_action=base_dimensions['pending_action'],
            service_type=other_service,
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
        'Pior motivo de corte',
    }

    for title in target_titles:
        assert title in by_title
        assert by_title[title]['summary']
        assert by_title[title]['operational_interpretation']
        assert by_title[title]['suggested_actions']
        assert by_title[title]['audit_recommendation']


@pytest.mark.django_db
def test_generate_insights_sem_acao_includes_specific_operational_recommendations(base_dimensions, interaction_factory):
    from apps.inbound.models import RetentionAction

    action_sem_acao = RetentionAction.objects.create(code='sem-acao', label='Sem acao', is_pending=False)

    for idx in range(5):
        interaction_factory(
            call_id_external=f'sem-acao-{idx}',
            retention_action=action_sem_acao,
        )

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    target = next(item for item in insights if item['title'] == 'Acao mais utilizada')
    assert target['value'] == 'Sem acao'
    assert target['operational_interpretation']
    assert target['suggested_actions']
    assert target['audit_recommendation']


@pytest.mark.django_db
def test_generate_insights_sem_acao_with_accent_normalizes_value(base_dimensions, interaction_factory):
    from apps.inbound.models import RetentionAction

    action_sem_acao = RetentionAction.objects.create(code='sem-acao-acc', label='Sem ação', is_pending=False)

    for idx in range(5):
        interaction_factory(
            call_id_external=f'sem-acao-acc-{idx}',
            retention_action=action_sem_acao,
        )

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    target = next(item for item in insights if item['title'] == 'Acao mais utilizada')
    assert target['value'] == 'Sem acao'
    assert target['operational_interpretation']


@pytest.mark.django_db
def test_generate_insights_pendente_keeps_original_label(base_dimensions, interaction_factory):
    action_pendente = base_dimensions['pending_action']

    for idx in range(5):
        interaction_factory(
            call_id_external=f'pendente-{idx}',
            retention_action=action_pendente,
        )

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': date(2026, 1, 1),
            'end_date': date(2026, 1, 31),
        }
    )

    target = next(item for item in insights if item['title'] == 'Acao mais utilizada')
    assert target['value'] == action_pendente.label
