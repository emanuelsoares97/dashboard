from django.db.models import Avg, Count, Q


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
        queryset.values('churn_reason_id', 'churn_reason__label')
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
        queryset.values('retention_action_id', 'retention_action__label')
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