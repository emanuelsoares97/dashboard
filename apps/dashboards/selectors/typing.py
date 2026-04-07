from apps.inbound.models import Interaction

from .base import apply_filters, get_inbound_queryset


def get_typing_queryset(filters: dict):
    """Devolve o queryset base para a análise de tipificações com os filtros activos."""
    qs = get_inbound_queryset()
    qs = apply_filters(
        qs,
        assistant_name=filters.get('assistant_name'),
        start_date=filters.get('start_date'),
        end_date=filters.get('end_date'),
        service_type_id=filters.get('service_type_id'),
        churn_reason_id=filters.get('churn_reason_id'),
    )
    return qs.select_related('agent', 'churn_reason').order_by('-occurred_on')
