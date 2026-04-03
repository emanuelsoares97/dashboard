from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek

from apps.inbound.models import Interaction
from apps.quality.models import DataQualityFlag


def get_inbound_queryset():
    """Devolve o queryset base de interacoes inbound para analise."""
    return Interaction.objects.filter(direction=Interaction.Direction.INBOUND)


def apply_filters(
    queryset,
    *,
    assistant_name=None,
    assistant_id=None,
    start_date=None,
    end_date=None,
    service_type_id=None,
    churn_reason_id=None,
    retention_action_id=None,
    final_outcome_id=None,
):
    """Aplica filtros opcionais comuns a todas as analises."""
    if assistant_id:
        queryset = queryset.filter(agent_id=assistant_id)
    if assistant_name:
        queryset = queryset.filter(agent__name__icontains=assistant_name)
    if start_date:
        queryset = queryset.filter(occurred_on__gte=start_date)
    if end_date:
        queryset = queryset.filter(occurred_on__lte=end_date)
    if service_type_id:
        queryset = queryset.filter(service_type_id=service_type_id)
    if churn_reason_id:
        queryset = queryset.filter(churn_reason_id=churn_reason_id)
    if retention_action_id:
        queryset = queryset.filter(retention_action_id=retention_action_id)
    if final_outcome_id:
        queryset = queryset.filter(final_outcome_id=final_outcome_id)
    return queryset


def select_global_filter_options(queryset):
    """Devolve opcoes reais de filtros globais com base no queryset atual."""
    service_types = [
        {'id': row['service_type_id'], 'label': row['service_type__label']}
        for row in queryset.exclude(service_type__isnull=True)
        .values('service_type_id', 'service_type__label')
        .distinct()
        .order_by('service_type__label')
    ]

    churn_reasons = [
        {
            'id': row['churn_reason_id'],
            'label': row['churn_reason__label'],
        }
        for row in queryset.exclude(churn_reason__isnull=True)
        .values('churn_reason_id', 'churn_reason__label')
        .distinct()
        .order_by('churn_reason__label')
    ]

    retention_actions = [
        {'id': row['retention_action_id'], 'label': row['retention_action__label']}
        for row in queryset.exclude(retention_action__isnull=True)
        .values('retention_action_id', 'retention_action__label')
        .distinct()
        .order_by('retention_action__label')
    ]

    final_outcomes = [
        {'id': row['final_outcome_id'], 'label': row['final_outcome__label']}
        for row in queryset.exclude(final_outcome__isnull=True)
        .values('final_outcome_id', 'final_outcome__label')
        .distinct()
        .order_by('final_outcome__label')
    ]

    return {
        'service_types': service_types,
        'churn_reasons': churn_reasons,
        'retention_actions': retention_actions,
        'final_outcomes': final_outcomes,
    }


def get_single_assistant_id(queryset, assistant_name):
    """Tenta resolver um unico assistente por nome exacto para abrir detalhe."""
    if not assistant_name:
        return None

    ids = list(
        queryset.filter(agent__name__iexact=assistant_name)
        .values_list('agent_id', flat=True)
        .distinct()[:2]
    )

    if len(ids) == 1:
        return ids[0]
    return None


def select_kpis_base(queryset):
    """Agrupa os totais principais para os KPIs gerais."""
    return queryset.aggregate(
        total_calls=Count('id'),
        total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
        total_call_drop=Count('id', filter=Q(is_call_drop=True)),
        avg_duration_seconds=Avg('duration_seconds'),
    )


def select_by_churn_reason(queryset):
    """Agrega resultados por motivo de churn."""
    return (
        queryset.values('churn_reason__label')
        .annotate(
            total_calls=Count('id'),
            total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
            total_call_drop=Count('id', filter=Q(is_call_drop=True)),
        )
        .order_by('-total_calls', 'churn_reason__label')
    )


def select_top_churn_reason_by_volume(queryset):
    """Devolve o motivo com maior volume de chamadas."""
    return (
        queryset.values('churn_reason__label')
        .annotate(total_calls=Count('id'))
        .order_by('-total_calls', 'churn_reason__label')
        .first()
    )


def select_by_retention_action(queryset):
    """Agrega resultados por acao de retencao."""
    return (
        queryset.values('retention_action__label')
        .annotate(
            total_used=Count('id'),
            total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
            total_call_drop=Count('id', filter=Q(is_call_drop=True)),
        )
        .order_by('-total_used', 'retention_action__label')
    )


def select_top_retention_action_by_volume(queryset):
    """Devolve a acao de retencao mais utilizada."""
    return (
        queryset.values('retention_action__label')
        .annotate(total_used=Count('id'))
        .order_by('-total_used', 'retention_action__label')
        .first()
    )


def select_by_service_type(queryset):
    """Agrega resultados por tipo de servico."""
    return (
        queryset.values('service_type__label')
        .annotate(
            total_calls=Count('id'),
            total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
            total_call_drop=Count('id', filter=Q(is_call_drop=True)),
        )
        .order_by('-total_calls', 'service_type__label')
    )


def select_temporal(queryset, granularity='day'):
    """Agrega resultados por dia, semana ou mes."""
    trunc_map = {
        'day': TruncDay('occurred_on'),
        'week': TruncWeek('occurred_on'),
        'month': TruncMonth('occurred_on'),
    }
    trunc_fn = trunc_map.get(granularity, trunc_map['day'])

    return (
        queryset.annotate(period=trunc_fn)
        .values('period')
        .annotate(
            total_calls=Count('id'),
            total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
            total_call_drop=Count('id', filter=Q(is_call_drop=True)),
        )
        .order_by('period')
    )


def select_assistant_ranking_base(queryset):
    """Agrega performance por assistente sem incluir equipas."""
    return (
        queryset.values('agent_id', 'agent__name')
        .annotate(
            total_calls=Count('id'),
            avg_duration_seconds=Avg('duration_seconds'),
            total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
            total_call_drop=Count('id', filter=Q(is_call_drop=True)),
        )
        .order_by('-total_calls', 'agent__name')
    )


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


def select_assistant_churn_breakdown(queryset):
    """Devolve top motivos de churn por assistente."""
    return (
        queryset.values('agent_id', 'agent__name', 'churn_reason__label')
        .annotate(
            total_calls=Count('id'),
            total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
        )
        .order_by('agent__name', '-total_calls')
    )


def select_assistant_action_breakdown(queryset):
    """Devolve utilizacao e eficacia de acoes por assistente."""
    return (
        queryset.values('agent_id', 'agent__name', 'retention_action__label')
        .annotate(
            total_used=Count('id'),
            total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
            avg_duration_seconds=Avg('duration_seconds'),
        )
        .order_by('agent__name', '-total_used')
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


def select_tipification_breakdown(queryset):
    """Agrega tipificacao (motivo + acao) para leitura de retidos e nao retidos."""
    return (
        queryset.values('churn_reason__label', 'retention_action__label')
        .annotate(
            total_calls=Count('id'),
            total_retained=Count('id', filter=Q(final_outcome__code='retido', is_call_drop=False)),
            total_call_drop=Count('id', filter=Q(is_call_drop=True)),
        )
        .order_by('-total_calls', 'churn_reason__label', 'retention_action__label')
    )
