from django.db.models import Count

from apps.quality.models import DataQualityFlag


def select_inconsistency_count_by_agent(queryset):
    """Conta inconsistencias por assistente para cruzar com o ranking."""
    base = DataQualityFlag.objects.filter(
        interaction__in=queryset,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
    )
    return {
        row['interaction__agent_id']: row['count']
        for row in base.values('interaction__agent_id').annotate(count=Count('id'))
    }


def select_inconsistency_by_assistant(queryset):
    """Devolve contagem de inconsistencias por assistente para leitura operacional."""
    return (
        DataQualityFlag.objects.filter(
            interaction__in=queryset,
            flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        )
        .values('interaction__agent_id', 'interaction__agent__name')
        .annotate(total_inconsistencies=Count('id'))
        .order_by('-total_inconsistencies', 'interaction__agent__name')
    )


def select_inconsistency_table(queryset):
    """Lista detalhe das inconsistencias para auditoria de tipificacao."""
    return (
        DataQualityFlag.objects.filter(
            interaction__in=queryset,
            flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
        )
        .values(
            'interaction__agent__name',
            'interaction__churn_reason__label',
            'interaction__retention_action__label',
            'interaction__final_outcome__label',
            'description',
        )
        .order_by('interaction__agent__name', 'interaction__churn_reason__label')
    )