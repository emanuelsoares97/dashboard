from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek

from apps.inbound.models import Interaction
from apps.quality.models import DataQualityFlag


def get_inbound_queryset():
    """Devolve o queryset base de interacoes inbound para analise."""
    return Interaction.objects.filter(direction=Interaction.Direction.INBOUND)


def apply_filters(queryset, *, assistant_name=None, assistant_id=None, start_date=None, end_date=None):
    """Aplica filtros opcionais comuns a todas as analises."""
    if assistant_id:
        queryset = queryset.filter(agent_id=assistant_id)
    if assistant_name:
        queryset = queryset.filter(agent__name__icontains=assistant_name)
    if start_date:
        queryset = queryset.filter(occurred_on__gte=start_date)
    if end_date:
        queryset = queryset.filter(occurred_on__lte=end_date)
    return queryset


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
