from datetime import date, timedelta

from django.utils import timezone

from apps.dashboards import selectors
from apps.dashboards.services.insights import generate_insights
from apps.dashboards.services.tables import (
    build_assistant_ranking_table,
    build_inconsistency_section,
    build_retention_action_table,
    calculate_general_kpis,
)
from apps.quality.models import DataQualityFlag


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
        (row for row in action_rows if row['retention_action'].strip().lower() in {'sem acao', 'pendente'}),
        None,
    )
    no_action_calls = no_action_row['total_used'] if no_action_row else 0

    return {
        'most_used': most_used,
        'highest_success': highest_success,
        'lowest_success': lowest_success,
        'no_action_pct': _pct(no_action_calls, total_calls),
    }


def _build_audit_calls(queryset, *, assistant_rows, low_retention_tipifications):
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
        reasons = []

        if interaction.agent_id in below_avg_assistant_ids:
            reasons.append('Assistente abaixo da media')

        action_label = interaction.retention_action.label if interaction.retention_action_id else 'Sem acao'
        if interaction.retention_action_id and interaction.retention_action.is_pending:
            reasons.append('Chamada sem acao registada')

        tipification_label = f"{interaction.churn_reason.label if interaction.churn_reason_id else 'Sem motivo'} | {action_label}"
        if tipification_label in low_retention_tipifications:
            reasons.append('Tipificacao com baixa retencao')

        has_inconsistency = any(
            flag.flag_type == DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY
            for flag in interaction.quality_flags.all()
        )
        if has_inconsistency:
            reasons.append('Inconsistencia de registo')

        if not reasons:
            continue

        calls.append(
            {
                'interaction_id': interaction.id,
                'call_id_external': interaction.call_id_external or f'#{interaction.id}',
                'assistant_name': interaction.agent.name,
                'occurred_on': interaction.occurred_on,
                'churn_reason': interaction.churn_reason.label if interaction.churn_reason_id else 'Sem motivo',
                'retention_action': action_label,
                'final_outcome': interaction.final_outcome.label,
                'priority_reasons': reasons,
                'priority_score': len(reasons),
            }
        )

    calls.sort(key=lambda item: (-item['priority_score'], item['assistant_name'], str(item['call_id_external'])))
    return calls[:25]


def build_previous_day_payload(filters: dict, *, reference_date: date | None = None) -> dict:
    """Constroi dados da aba Dia anterior com foco operacional."""
    previous_day = _resolve_previous_day(reference_date)

    base_qs = selectors.get_inbound_queryset()
    day_qs = selectors.apply_filters(
        base_qs,
        start_date=previous_day,
        end_date=previous_day,
        service_type_id=filters.get('service_type_id'),
        churn_reason_id=filters.get('churn_reason_id'),
        retention_action_id=filters.get('retention_action_id'),
        final_outcome_id=filters.get('final_outcome_id'),
    )

    kpis = calculate_general_kpis(day_qs)
    total_calls = kpis['total_calls']

    no_action_calls = day_qs.filter(retention_action__is_pending=True).count()
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
    actions_summary = _build_actions_summary(actions_rows, total_calls=total_calls)

    insights = generate_insights(
        {
            'assistant_name': '',
            'start_date': previous_day,
            'end_date': previous_day,
            'service_type_id': filters.get('service_type_id'),
            'churn_reason_id': filters.get('churn_reason_id'),
            'retention_action_id': filters.get('retention_action_id'),
            'final_outcome_id': filters.get('final_outcome_id'),
        }
    )

    audit_calls = _build_audit_calls(
        day_qs,
        assistant_rows=assistant_rows,
        low_retention_tipifications=tipification['low_retention_labels'],
    )

    return {
        'day': previous_day,
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
