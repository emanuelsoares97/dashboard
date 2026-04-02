from datetime import datetime, timedelta, timezone

import pytest

from apps.imports_app.models import ImportBatch
from apps.inbound.models import Agent, ChurnReason, Interaction, OutcomeFinal, RetentionAction, ServiceType, Team


@pytest.fixture
def base_dimensions(db):
    """Cria dimensoes base reutilizaveis para testes de dashboard e selectors."""
    team = Team.objects.create(name='Equipa A')
    agent = Agent.objects.create(team=team, name='Ana')
    retained = OutcomeFinal.objects.create(code='retido', label='Retido')
    not_retained = OutcomeFinal.objects.create(code='nao_retido', label='Nao Retido')
    action = RetentionAction.objects.create(code='oferta', label='Oferta')
    pending_action = RetentionAction.objects.create(code='pendente', label='Pendente', is_pending=True)
    reason = ChurnReason.objects.create(code='preco', label='Preco')
    service = ServiceType.objects.create(code='fibra', label='Fibra')
    batch = ImportBatch.objects.create(original_filename='fixture.xlsx')

    return {
        'team': team,
        'agent': agent,
        'retained': retained,
        'not_retained': not_retained,
        'action': action,
        'pending_action': pending_action,
        'reason': reason,
        'service': service,
        'batch': batch,
    }


@pytest.fixture
def interaction_factory(db, base_dimensions):
    """Factory simples para criar interacoes inbound com defaults coerentes."""

    def _factory(**overrides):
        start_at = overrides.pop('start_at', datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc))
        end_at = overrides.pop('end_at', start_at + timedelta(minutes=5))

        defaults = {
            'batch': base_dimensions['batch'],
            'direction': Interaction.Direction.INBOUND,
            'team': base_dimensions['team'],
            'agent': base_dimensions['agent'],
            'call_id_external': 'call-1',
            'start_at': start_at,
            'end_at': end_at,
            'final_outcome': base_dimensions['retained'],
            'retention_action': base_dimensions['action'],
            'churn_reason': base_dimensions['reason'],
            'service_type': base_dimensions['service'],
            'is_call_drop': False,
            'metadata': {},
        }
        defaults.update(overrides)
        return Interaction.objects.create(**defaults)

    return _factory
