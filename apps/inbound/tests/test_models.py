from datetime import datetime, timedelta, timezone

import pytest
from django.core.exceptions import ValidationError

from apps.imports_app.models import ImportBatch
from apps.inbound.models import Agent, Interaction, OutcomeFinal, RetentionAction, Team


@pytest.mark.django_db
def test_interaction_save_updates_duration_and_occurred_on():
    team = Team.objects.create(name='Team Save')
    agent = Agent.objects.create(team=team, name='Agente Save')
    batch = ImportBatch.objects.create(original_filename='model.xlsx')
    outcome = OutcomeFinal.objects.create(code='retido', label='Retido')
    action = RetentionAction.objects.create(code='oferta', label='Oferta')

    start_at = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
    end_at = start_at + timedelta(minutes=7)

    interaction = Interaction.objects.create(
        batch=batch,
        team=team,
        agent=agent,
        start_at=start_at,
        end_at=end_at,
        final_outcome=outcome,
        retention_action=action,
        direction=Interaction.Direction.INBOUND,
    )

    assert interaction.duration_seconds == 420
    assert interaction.occurred_on.isoformat() == '2026-01-10'


@pytest.mark.django_db
def test_interaction_clean_raises_when_agent_does_not_belong_to_team():
    team_a = Team.objects.create(name='Team A')
    team_b = Team.objects.create(name='Team B')
    agent = Agent.objects.create(team=team_a, name='Agente Mismatch')
    batch = ImportBatch.objects.create(original_filename='mismatch.xlsx')
    outcome = OutcomeFinal.objects.create(code='nao_retido', label='Nao Retido')
    action = RetentionAction.objects.create(code='pendente', label='Pendente', is_pending=True)

    interaction = Interaction(
        batch=batch,
        team=team_b,
        agent=agent,
        start_at=datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 10, 12, 5, tzinfo=timezone.utc),
        final_outcome=outcome,
        retention_action=action,
        direction=Interaction.Direction.INBOUND,
    )

    with pytest.raises(ValidationError):
        interaction.clean()
