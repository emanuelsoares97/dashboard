from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.functions import Trim

from apps.inbound.models import Interaction


OUTBOUND_CATEGORY_VALUE = 'cc ret outbound'


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
    subcategory_exclude_values=None,
    churn_reason_exclude_labels=None,
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
            queryset = queryset.annotate(
                _subcategory_normalized=Lower(Trim('subcategory')),
                _category_normalized=Lower(Trim('category')),
            )
            outbound_requested = OUTBOUND_CATEGORY_VALUE in normalized_values
            remaining_values = normalized_values - {OUTBOUND_CATEGORY_VALUE}

            if outbound_requested and remaining_values:
                queryset = queryset.filter(
                    Q(_category_normalized=OUTBOUND_CATEGORY_VALUE)
                    | Q(_subcategory_normalized__in=remaining_values)
                )
            elif outbound_requested:
                queryset = queryset.filter(_category_normalized=OUTBOUND_CATEGORY_VALUE)
            else:
                queryset = queryset.filter(_subcategory_normalized__in=remaining_values)
    if subcategory_exclude_values:
        normalized_excluded_values = {
            str(value).strip().lower()
            for value in subcategory_exclude_values
            if str(value).strip()
        }
        if normalized_excluded_values:
            queryset = queryset.annotate(
                _subcategory_normalized=Lower(Trim('subcategory')),
                _category_normalized=Lower(Trim('category')),
            )
            outbound_excluded = OUTBOUND_CATEGORY_VALUE in normalized_excluded_values
            remaining_excluded = normalized_excluded_values - {OUTBOUND_CATEGORY_VALUE}

            if outbound_excluded:
                queryset = queryset.exclude(_category_normalized=OUTBOUND_CATEGORY_VALUE)
            if remaining_excluded:
                queryset = queryset.exclude(_subcategory_normalized__in=remaining_excluded)
    if churn_reason_exclude_labels:
        normalized_excluded_labels = {
            str(label).strip().lower()
            for label in churn_reason_exclude_labels
            if str(label).strip()
        }
        if normalized_excluded_labels:
            queryset = queryset.annotate(
                _churn_reason_normalized=Lower(Trim('churn_reason__label'))
            ).exclude(_churn_reason_normalized__in=normalized_excluded_labels)
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