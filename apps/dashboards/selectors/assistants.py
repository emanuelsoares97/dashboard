from django.db.models import Avg, Count, Q


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