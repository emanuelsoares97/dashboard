from django.db import migrations


OUTBOUND_CATEGORY_VALUE = 'cc ret outbound'


def forwards(apps, schema_editor):
    Interaction = apps.get_model('inbound', 'Interaction')
    OutboundInteraction = apps.get_model('inbound', 'OutboundInteraction')

    outbound_rows = Interaction.objects.filter(category__iexact=OUTBOUND_CATEGORY_VALUE)

    for row in outbound_rows.iterator(chunk_size=1000):
        OutboundInteraction.objects.create(
            batch_id=row.batch_id,
            call_id_external=row.call_id_external,
            team_id=row.team_id,
            agent_id=row.agent_id,
            start_at=row.start_at,
            end_at=row.end_at,
            duration_seconds=row.duration_seconds,
            occurred_on=row.occurred_on,
            final_outcome_id=row.final_outcome_id,
            retention_action_id=row.retention_action_id,
            churn_reason_id=row.churn_reason_id,
            service_type_id=row.service_type_id,
            is_call_drop=row.is_call_drop,
            category=row.category,
            subcategory=row.subcategory,
            observations=row.observations,
            metadata=row.metadata,
            created_at=row.created_at,
        )

    outbound_rows.delete()


def backwards(apps, schema_editor):
    Interaction = apps.get_model('inbound', 'Interaction')
    OutboundInteraction = apps.get_model('inbound', 'OutboundInteraction')

    for row in OutboundInteraction.objects.all().iterator(chunk_size=1000):
        Interaction.objects.create(
            batch_id=row.batch_id,
            direction='inbound',
            call_id_external=row.call_id_external,
            team_id=row.team_id,
            agent_id=row.agent_id,
            start_at=row.start_at,
            end_at=row.end_at,
            duration_seconds=row.duration_seconds,
            occurred_on=row.occurred_on,
            final_outcome_id=row.final_outcome_id,
            retention_action_id=row.retention_action_id,
            churn_reason_id=row.churn_reason_id,
            service_type_id=row.service_type_id,
            is_call_drop=row.is_call_drop,
            category=row.category,
            subcategory=row.subcategory,
            observations=row.observations,
            metadata=row.metadata,
            created_at=row.created_at,
        )

    OutboundInteraction.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inbound', '0007_outboundinteraction'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
