from django.db.models.functions import Lower
from django.db.models.functions import Trim

from apps.inbound.models import Interaction


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
    subcategory_exact_values=None,
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
    if subcategory_exact_values:
        normalized_values = {
            str(value).strip().lower()
            for value in subcategory_exact_values
            if str(value).strip()
        }
        if normalized_values:
            queryset = queryset.annotate(_subcategory_normalized=Lower(Trim('subcategory'))).filter(
                _subcategory_normalized__in=normalized_values
            )
    return queryset


def select_global_filter_options(queryset):
    """Devolve opcoes reais de filtros globais com base no queryset atual."""
    assistants = [
        {'id': row['agent_id'], 'name': row['agent__name']}
        for row in queryset.exclude(agent__isnull=True)
        .values('agent_id', 'agent__name')
        .distinct()
        .order_by('agent__name')
    ]

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
        'assistants': assistants,
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