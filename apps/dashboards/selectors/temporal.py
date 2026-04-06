from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek


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