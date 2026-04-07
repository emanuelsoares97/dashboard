from django.utils.text import slugify

from apps.imports_app.models import ImportBatch, ImportRowRaw
from apps.imports_app.types import ImportRowData, QualityFlagInput
from apps.inbound.models import (
    Agent,
    ChurnReason,
    Interaction,
    OutcomeFinal,
    RetentionAction,
    ServiceType,
    Team,
)
from apps.quality.models import DataQualityFlag


def make_code(value: str, fallback: str) -> str:
    code = slugify(value).replace('-', '_')
    return code or fallback


def create_raw_row(
    batch: ImportBatch,
    row_number: int,
    raw_payload: dict[str, str],
    raw_hash: str,
    processing_status: str = ImportRowRaw.ProcessingStatus.IMPORTED,
    processing_error: str = '',
) -> ImportRowRaw:
    return ImportRowRaw.objects.create(
        batch=batch,
        source_row_number=row_number,
        raw_payload=raw_payload,
        raw_hash=raw_hash,
        processing_status=processing_status,
        processing_error=processing_error,
    )


def get_team(name: str) -> Team:
    team, _ = Team.objects.get_or_create(name=name)
    return team


def get_agent(team: Team, name: str) -> Agent:
    agent, _ = Agent.objects.get_or_create(team=team, name=name)
    return agent


def get_outcome(label: str, is_call_drop: bool) -> OutcomeFinal:
    outcome, _ = OutcomeFinal.objects.get_or_create(
        code=make_code(label, 'outcome_unknown'),
        defaults={
            'label': label,
            'is_call_drop_outcome': is_call_drop,
        },
    )
    if is_call_drop and not outcome.is_call_drop_outcome:
        outcome.is_call_drop_outcome = True
        outcome.save(update_fields=['is_call_drop_outcome'])
    return outcome


def get_retention_action(label: str) -> RetentionAction:
    return RetentionAction.objects.get_or_create(
        code=make_code(label, 'retention_action_unknown'),
        defaults={
            'label': label,
            'is_pending': label.lower() == 'pendente',
        },
    )[0]


def get_churn_reason(label: str):
    if not label:
        return None
    return ChurnReason.objects.get_or_create(
        code=make_code(label, 'churn_reason_unknown'),
        defaults={'label': label},
    )[0]


def get_service_type(label: str):
    if not label:
        return None
    return ServiceType.objects.get_or_create(
        code=make_code(label, 'service_type_unknown'),
        defaults={'label': label},
    )[0]


def persist_interaction(
    batch: ImportBatch,
    raw_row: ImportRowRaw,
    row_data: ImportRowData,
    quality_flags: list[QualityFlagInput],
) -> tuple[Interaction, int]:
    # A V1 nao recebe equipa no Excel; usamos uma equipa tecnica por defeito.
    team = get_team('Sem Equipa Definida')
    agent = get_agent(team, row_data.agent_name)
    outcome_label = 'Call Drop' if row_data.is_call_drop else row_data.final_outcome
    action_label = row_data.retention_action

    interaction = Interaction.objects.create(
        batch=batch,
        direction=Interaction.Direction.INBOUND,
        call_id_external=row_data.external_call_id,
        team=team,
        agent=agent,
        start_at=row_data.start_at,
        end_at=row_data.end_at,
        occurred_on=row_data.start_at.date(),
        final_outcome=get_outcome(outcome_label, row_data.is_call_drop),
        retention_action=get_retention_action(action_label),
        churn_reason=get_churn_reason(row_data.churn_reason),
        service_type=get_service_type(row_data.service_type),
        is_call_drop=row_data.is_call_drop,
        category=row_data.category,
        subcategory=row_data.subcategory,
        observations=row_data.observations,
        metadata={
            'source': 'manual_excel',
            'original_ret_resolution': row_data.final_outcome,
            'original_resolution': row_data.retention_action,
            'day': row_data.day,
            'week': row_data.week,
            'month': row_data.month,
            'exclude': row_data.exclude,
        },
    )

    raw_row.processed_interaction = interaction
    raw_row.save(update_fields=['processed_interaction'])

    for flag in quality_flags:
        DataQualityFlag.objects.create(
            interaction=interaction,
            flag_type=flag.flag_type,
            rule_code=flag.rule_code,
            severity=flag.severity,
            description=flag.description,
        )

    return interaction, len(quality_flags)
