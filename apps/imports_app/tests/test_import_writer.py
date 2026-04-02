from datetime import datetime, timezone

import pytest

from apps.imports_app.models import ImportBatch, ImportRowRaw
from apps.imports_app.persistence.import_writer import (
    create_raw_row,
    get_churn_reason,
    get_outcome,
    get_retention_action,
    get_service_type,
    make_code,
    persist_interaction,
)
from apps.imports_app.types import ImportRowData, QualityFlagInput
from apps.quality.models import DataQualityFlag


@pytest.mark.django_db
def test_make_code_uses_fallback_when_slug_is_empty():
    assert make_code('###', 'fallback_code') == 'fallback_code'


@pytest.mark.django_db
def test_create_raw_row_persists_status_and_error():
    batch = ImportBatch.objects.create(original_filename='writer.xlsx')

    raw_row = create_raw_row(
        batch=batch,
        row_number=2,
        raw_payload={'agent_name': 'Ana'},
        raw_hash='abc123',
        processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_IN_FILE,
        processing_error='Duplicada no ficheiro',
    )

    assert raw_row.processing_status == ImportRowRaw.ProcessingStatus.DUPLICATE_IN_FILE
    assert raw_row.processing_error == 'Duplicada no ficheiro'


@pytest.mark.django_db
def test_get_optional_dimensions_return_none_for_empty_labels():
    assert get_churn_reason('') is None
    assert get_service_type('') is None


@pytest.mark.django_db
def test_get_outcome_upgrades_call_drop_flag_for_existing_outcome():
    outcome = get_outcome('Call Drop', False)
    assert outcome.is_call_drop_outcome is False

    upgraded = get_outcome('Call Drop', True)
    assert upgraded.id == outcome.id
    assert upgraded.is_call_drop_outcome is True


@pytest.mark.django_db
def test_get_retention_action_sets_pending_flag_when_label_is_pendente():
    action = get_retention_action('Pendente')

    assert action.is_pending is True


@pytest.mark.django_db
def test_persist_interaction_creates_relations_and_quality_flags():
    batch = ImportBatch.objects.create(original_filename='persist.xlsx')
    raw_row = create_raw_row(
        batch=batch,
        row_number=2,
        raw_payload={'agent_name': 'Ana'},
        raw_hash='hash-persist',
    )
    row_data = ImportRowData(
        row_number=2,
        raw_payload={'agent_name': 'Ana'},
        external_call_id='call-100',
        agent_name='Ana',
        start_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 1, 10, 4, tzinfo=timezone.utc),
        final_outcome='Retido',
        retention_action='Oferta',
        churn_reason='Preco',
        service_type='Fibra',
        is_call_drop=False,
        day='2026-01-01',
        week='2026-W01',
        month='2026-01',
        exclude='',
    )
    flags = [
        QualityFlagInput(
            flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
            rule_code='rule_1',
            severity=DataQualityFlag.Severity.WARNING,
            description='Inconsistencia de teste',
        )
    ]

    interaction, created_flags = persist_interaction(batch, raw_row, row_data, flags)

    raw_row.refresh_from_db()
    assert interaction.batch_id == batch.id
    assert interaction.agent.name == 'Ana'
    assert interaction.team.name == 'Sem Equipa Definida'
    assert raw_row.processed_interaction_id == interaction.id
    assert created_flags == 1
    assert DataQualityFlag.objects.filter(interaction=interaction).count() == 1


@pytest.mark.django_db
def test_persist_interaction_without_optional_dimensions_creates_interaction():
    batch = ImportBatch.objects.create(original_filename='persist-empty.xlsx')
    raw_row = create_raw_row(
        batch=batch,
        row_number=2,
        raw_payload={'agent_name': 'Ana'},
        raw_hash='hash-empty',
    )
    row_data = ImportRowData(
        row_number=2,
        raw_payload={'agent_name': 'Ana'},
        external_call_id='call-200',
        agent_name='Ana',
        start_at=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 2, 10, 1, tzinfo=timezone.utc),
        final_outcome='Call Drop',
        retention_action='Pendente',
        churn_reason='',
        service_type='',
        is_call_drop=True,
        day='2026-01-02',
        week='2026-W01',
        month='2026-01',
        exclude='',
    )

    interaction, created_flags = persist_interaction(batch, raw_row, row_data, [])

    assert interaction.churn_reason is None
    assert interaction.service_type is None
    assert interaction.is_call_drop is True
    assert created_flags == 0
