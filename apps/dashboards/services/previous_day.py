from datetime import date, timedelta

from django.utils import timezone

from apps.dashboards import selectors
from apps.dashboards.services.label_normalization import build_normalized_set
from apps.dashboards.services.label_normalization import is_label_in
from apps.dashboards.services.insights import generate_insights
from apps.dashboards.services.tables import (
    build_assistant_ranking_table,
    build_inconsistency_section,
    build_retention_action_table,
    calculate_general_kpis,
)
from apps.quality.models import DataQualityFlag


NON_RETAINED_LABELS = {'nao retido'}
NO_ACTION_LABELS = {'sem acao', 'sem ação', 'sem acao registada'}
HIGH_AUDIT_THIRD_CATEGORIES = {
    'concorrencia',
    'concorrência',
    'problema faturacao',
    'problema faturação',
    'problema tecnico fibra',
    'problema técnico fibra',
    'problema tecnico movel',
    'problema técnico movel',
    'conteudos da tv',
    'conteúdos da tv',
    'canais premium',
}

NORMALIZED_NON_RETAINED_LABELS = build_normalized_set(NON_RETAINED_LABELS)
NORMALIZED_NO_ACTION_LABELS = build_normalized_set(NO_ACTION_LABELS)
NORMALIZED_HIGH_AUDIT_THIRD_CATEGORIES = build_normalized_set(HIGH_AUDIT_THIRD_CATEGORIES)


def _is_no_action_label(label: str | None) -> bool:
    return is_label_in(label, NORMALIZED_NO_ACTION_LABELS)


def _is_not_retained_outcome(label: str | None) -> bool:
    return is_label_in(label, NORMALIZED_NON_RETAINED_LABELS)


def _is_high_audit_third_category(label: str | None) -> bool:
    return is_label_in(label, NORMALIZED_HIGH_AUDIT_THIRD_CATEGORIES)


def _pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _resolve_previous_day(reference_date: date | None = None) -> date:
    base = reference_date or timezone.localdate()
    return base - timedelta(days=1)


def _build_tipification_summary(queryset):
    rows = []
    for row in selectors.select_tipification_breakdown(queryset):
        total_calls = row['total_calls'] or 0
        if total_calls <= 0:
            continue

        total_retained = row['total_retained'] or 0
        total_call_drop = row['total_call_drop'] or 0
        total_non_retained = max(total_calls - total_retained - total_call_drop, 0)

        churn_reason = row['churn_reason__label'] or 'Sem motivo'
        retention_action = row['retention_action__label'] or 'Sem acao'

        rows.append(
            {
                'tipification_label': f'{churn_reason} | {retention_action}',
                'total_calls': total_calls,
                'retention_rate': _pct(total_retained, total_calls),
                'non_retention_rate': _pct(total_non_retained, total_calls),
            }
        )

    if not rows:
        return {
            'best': None,
            'worst': None,
            'low_retention_labels': set(),
        }

    best = max(rows, key=lambda item: (item['retention_rate'], item['total_calls']))
    worst = min(rows, key=lambda item: (item['retention_rate'], -item['total_calls']))

    low_retention_labels = {
        item['tipification_label']
        for item in rows
        if item['retention_rate'] < 40 and item['total_calls'] >= 2
    }

    return {
        'best': best,
        'worst': worst,
        'low_retention_labels': low_retention_labels,
    }


def _build_actions_summary(action_rows, *, total_calls: int):
    if not action_rows:
        return {
            'most_used': None,
            'highest_success': None,
            'lowest_success': None,
            'no_action_pct': 0.0,
        }

    most_used = max(action_rows, key=lambda item: (item['total_used'], item['success_rate']))

    rows_with_usage = [row for row in action_rows if row['total_used'] > 0]
    if not rows_with_usage:
        return {
            'most_used': most_used,
            'highest_success': None,
            'lowest_success': None,
            'no_action_pct': 0.0,
        }

    highest_success = max(rows_with_usage, key=lambda item: (item['success_rate'], item['total_used']))
    lowest_success = min(rows_with_usage, key=lambda item: (item['success_rate'], -item['total_used']))

    no_action_row = next(
        (row for row in action_rows if _is_no_action_label(row['retention_action'])),
        None,
    )
    no_action_calls = no_action_row['total_used'] if no_action_row else 0

    return {
        'most_used': most_used,
        'highest_success': highest_success,
        'lowest_success': lowest_success,
        'no_action_pct': _pct(no_action_calls, total_calls),
    }


def _calculate_audit_priority_score(interaction, *, below_avg_assistant_ids, low_retention_tipifications) -> tuple[int, list[str]]:
    """
    Calcula score de prioridade (0-100) e lista de motivos para auditoria.
    
    Pesos principais:
    - Cliente nao retido: 25
    - Sem acao de retencao registada: 30
    - Third category com alto potencial de retencao: 20
    - Assistente abaixo da media: 15
    - Inconsistencia: 10
    - Alta taxa de nao retencao no servico/tipificacao: 10
    """
    score = 0
    reasons = []
    
    # Base: cliente nao retido
    score += 25
    reasons.append('Cliente nao foi retido')

    # Sem acao de retencao
    action_label = interaction.retention_action.label if interaction.retention_action_id else 'Sem acao'
    if _is_no_action_label(action_label):
        score += 30
        reasons.append('Sem acao de retencao registada')

    third_category_label = interaction.churn_reason.label if interaction.churn_reason_id else ''
    if _is_high_audit_third_category(third_category_label):
        score += 20
        reasons.append('Tipificacao com potencial de retencao')
    
    # Assistente abaixo da média (peso: 25)
    if interaction.agent_id in below_avg_assistant_ids:
        score += 15
        reasons.append('Assistente abaixo da media')
    
    # Inconsistência (peso: 20)
    has_inconsistency = any(
        flag.flag_type == DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY
        for flag in interaction.quality_flags.all()
    )
    if has_inconsistency:
        score += 10
        reasons.append('Inconsistencia de registo')
    
    # Baixa retencao do servico/tipificacao
    tipification_label = f"{interaction.churn_reason.label if interaction.churn_reason_id else 'Sem motivo'} | {action_label}"
    if tipification_label in low_retention_tipifications:
        score += 10
        reasons.append('Alta taxa de nao retencao neste servico')
    
    return min(score, 100), reasons


def _build_audit_calls(queryset, *, assistant_rows, low_retention_tipifications):
    """
    Constrói lista de chamadas para auditoria, priorizadas por score.
    
    Retorna top 15 chamadas ordenadas por score descrescente.
    """
    if not queryset.exists():
        return []

    avg_retention = 0.0
    if assistant_rows:
        avg_retention = sum(row['retention_rate'] for row in assistant_rows) / len(assistant_rows)

    below_avg_assistant_ids = {
        row['assistant_id']
        for row in assistant_rows
        if row['retention_rate'] < avg_retention
    }

    calls = []
    interactions = (
        queryset.select_related('agent', 'retention_action', 'churn_reason', 'final_outcome')
        .prefetch_related('quality_flags')
        .order_by('-start_at')
    )

    for interaction in interactions:
        if not _is_not_retained_outcome(interaction.final_outcome.label):
            continue

        priority_score, audit_reasons = _calculate_audit_priority_score(
            interaction,
            below_avg_assistant_ids=below_avg_assistant_ids,
            low_retention_tipifications=low_retention_tipifications,
        )
        
        if not audit_reasons:
            continue

        action_label = interaction.retention_action.label if interaction.retention_action_id else 'Sem acao'
        
        calls.append(
            {
                'interaction_id': interaction.id,
                'call_id_external': interaction.call_id_external or f'#{interaction.id}',
                'assistant_name': interaction.agent.name,
                'occurred_on': interaction.occurred_on,
                'observations': interaction.observations,
                'category': interaction.category,
                'subcategory': interaction.subcategory,
                'third_category': interaction.churn_reason.label if interaction.churn_reason_id else '',
                'churn_reason': interaction.churn_reason.label if interaction.churn_reason_id else 'Sem motivo',
                'retention_action': action_label,
                'final_outcome': interaction.final_outcome.label,
                'audit_priority_score': priority_score,
                'audit_reasons': audit_reasons,
            }
        )

    calls.sort(key=lambda item: (-item['audit_priority_score'], item['assistant_name'], str(item['call_id_external'])))
    return calls[:15]


def build_previous_day_payload(
    filters: dict,
    *,
    reference_date: date | None = None,
    target_day: date | None = None,
) -> dict:
    """Constroi dados da aba Dia anterior com foco operacional."""
    selected_day = target_day or _resolve_previous_day(reference_date)

    base_qs = selectors.get_inbound_queryset()
    day_qs = selectors.apply_filters(
        base_qs,
        start_date=selected_day,
        end_date=selected_day,
        service_type_id=filters.get('service_type_id'),
        churn_reason_id=filters.get('churn_reason_id'),
        retention_action_id=filters.get('retention_action_id'),
        final_outcome_id=filters.get('final_outcome_id'),
        subcategory_exact_values=filters.get('subcategory_exact_values'),
        subcategory_exclude_values=filters.get('subcategory_exclude_values'),
    )

    kpis = calculate_general_kpis(day_qs)
    total_calls = kpis['total_calls']
    inconsistency_section = build_inconsistency_section(day_qs)

    assistant_rows = [row for row in build_assistant_ranking_table(day_qs) if row['total_calls'] > 0]
    top_assistants = sorted(
        assistant_rows,
        key=lambda item: (-item['retention_rate'], -item['total_calls'], item['assistant_name']),
    )[:3]
    bottom_assistants = sorted(
        assistant_rows,
        key=lambda item: (item['retention_rate'], -item['total_calls'], item['assistant_name']),
    )[:3]

    tipification = _build_tipification_summary(day_qs)

    actions_rows = build_retention_action_table(day_qs)
    no_action_calls = sum(
        row['total_used']
        for row in actions_rows
        if _is_no_action_label(row['retention_action'])
    )
    actions_summary = _build_actions_summary(actions_rows, total_calls=total_calls)

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': selected_day,
            'end_date': selected_day,
            'service_type_id': filters.get('service_type_id'),
            'churn_reason_id': filters.get('churn_reason_id'),
            'retention_action_id': filters.get('retention_action_id'),
            'final_outcome_id': filters.get('final_outcome_id'),
            'subcategory_exact_values': filters.get('subcategory_exact_values'),
            'subcategory_exclude_values': filters.get('subcategory_exclude_values'),
        }
    )

    audit_calls = _build_audit_calls(
        day_qs,
        assistant_rows=assistant_rows,
        low_retention_tipifications=tipification['low_retention_labels'],
    )

    return {
        'day': selected_day,
        'kpis': {
            **kpis,
            'no_action_pct': _pct(no_action_calls, total_calls),
            'inconsistency_rate': inconsistency_section['kpis']['global_inconsistency_rate'],
        },
        'assistants': {
            'top': top_assistants,
            'bottom': bottom_assistants,
        },
        'tipification': {
            'best': tipification['best'],
            'worst': tipification['worst'],
        },
        'actions': actions_summary,
        'insights': insights,
        'audit_calls': audit_calls,
    }
