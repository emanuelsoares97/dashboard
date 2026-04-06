from apps.dashboards import selectors
from apps.dashboards.services.comparison import _build_assistant_comparison_table
from apps.dashboards.services.comparison import _build_assistant_detail_comparison
from apps.dashboards.services.comparison import _build_churn_reason_comparison_table
from apps.dashboards.services.comparison import _build_comparison_block
from apps.dashboards.services.comparison import _build_inconsistency_comparison_section
from apps.dashboards.services.comparison import _build_retention_action_comparison_table
from apps.dashboards.services.comparison import _build_service_type_comparison_table
from apps.dashboards.services.tables import _pct
from apps.dashboards.services.tables import _round2
from apps.dashboards.services.tables import build_assistant_ranking_table
from apps.dashboards.services.tables import build_churn_reason_table
from apps.dashboards.services.tables import build_daily_rates_table
from apps.dashboards.services.tables import build_inconsistency_section
from apps.dashboards.services.tables import build_monthly_rates_table
from apps.dashboards.services.tables import build_retention_action_table
from apps.dashboards.services.tables import build_service_type_table
from apps.dashboards.services.tables import build_temporal_table
from apps.dashboards.services.tables import build_tipification_tables
from apps.dashboards.services.tables import calculate_general_kpis


LOW_SAMPLE_CALLS_THRESHOLD = 10


def _take_top(rows, key, limit=8):
    return sorted(rows, key=lambda item: item.get(key, 0), reverse=True)[:limit]


def _build_ui_state(general_kpis):
    """Prepara estado global da pagina para vazio e amostra reduzida."""
    total_calls = general_kpis['total_calls']
    is_low_sample = 0 < total_calls < LOW_SAMPLE_CALLS_THRESHOLD
    return {
        'has_data': total_calls > 0,
        'empty_message': 'Sem dados para os filtros selecionados.',
        'is_low_sample': is_low_sample,
        'warning_message': 'A amostra atual e reduzida; interpretar os resultados com cautela.',
    }


def _build_table_states(*, churn_reason_table, retention_action_table, service_type_table, monthly_rates_table, assistant_ranking_table, inconsistency_section):
    """Define estados de vazio consistentes para tabelas principais."""
    default_empty_message = 'Nao existem registos para apresentar.'
    return {
        'default_empty_message': default_empty_message,
        'assistants': {
            'has_data': bool(assistant_ranking_table),
            'empty_message': default_empty_message,
        },
        'services': {
            'has_data': bool(service_type_table),
            'empty_message': default_empty_message,
        },
        'inconsistencies': {
            'has_data': bool(inconsistency_section['table']),
            'empty_message': default_empty_message,
        },
        'monthly_rates': {
            'has_data': bool(monthly_rates_table),
            'empty_message': default_empty_message,
        },
        'churn_reasons': {
            'has_data': bool(churn_reason_table),
            'empty_message': default_empty_message,
        },
        'retention_actions': {
            'has_data': bool(retention_action_table),
            'empty_message': default_empty_message,
        },
    }


def build_assistant_detail(queryset, assistant_id, granularity='day'):
    """Gera analise detalhada para um assistente especifico."""
    assistant_qs = queryset.filter(agent_id=assistant_id)

    churn_rows = []
    assistant_total_calls = assistant_qs.count()
    for row in selectors.select_assistant_churn_breakdown(assistant_qs):
        total_calls = row['total_calls'] or 0
        retained = row['total_retained'] or 0
        churn_rows.append(
            {
                'assistant_id': row['agent_id'],
                'assistant_name': row['agent__name'] or 'Sem assistente',
                'churn_reason': row['churn_reason__label'] or 'Sem motivo',
                'total_calls': total_calls,
                'pct_total': _pct(total_calls, assistant_total_calls),
                'retention_rate': _pct(retained, total_calls),
            }
        )

    action_rows = []
    for row in selectors.select_assistant_action_breakdown(assistant_qs):
        total_used = row['total_used'] or 0
        retained = row['total_retained'] or 0
        action_rows.append(
            {
                'assistant_id': row['agent_id'],
                'assistant_name': row['agent__name'] or 'Sem assistente',
                'retention_action': row['retention_action__label'] or 'Sem acao',
                'total_used': total_used,
                'success_rate': _pct(retained, total_used),
                'avg_duration_seconds': _round2(row['avg_duration_seconds']),
            }
        )

    base_kpis = calculate_general_kpis(assistant_qs)
    temporal_table = build_temporal_table(assistant_qs, granularity=granularity)
    tipification_tables = build_tipification_tables(assistant_qs)

    return {
        'kpis': base_kpis,
        'top_churn_reasons': churn_rows,
        'retention_actions': action_rows,
        'temporal_table': temporal_table,
        'avg_duration_seconds': base_kpis['avg_duration_seconds'],
        'tipification_non_retained': tipification_tables['non_retained'],
        'tipification_retained': tipification_tables['retained'],
        'frontend_payload': build_frontend_payload(
            general_kpis=base_kpis,
            temporal_table=temporal_table,
            churn_reason_table=churn_rows,
            retention_action_table=action_rows,
        ),
    }


def build_frontend_payload(*, general_kpis, temporal_table, churn_reason_table, retention_action_table):
    """Prepara estruturas simples e diretas para o frontend e para o Chart.js."""
    top_reasons = _take_top(churn_reason_table, 'total_calls')
    top_actions = _take_top(retention_action_table, 'total_used')

    return {
        'outcomes_chart': {
            'labels': ['Retidos', 'Nao Retidos', 'Call Drop'],
            'datasets': [
                {
                    'data': [
                        general_kpis['total_retained'],
                        general_kpis['total_non_retained'],
                        general_kpis['total_call_drop'],
                    ]
                }
            ],
        },
        'temporal_chart': {
            'labels': [row['period'] for row in temporal_table],
            'datasets': [
                {
                    'label': 'Taxa Retencao (%)',
                    'data': [row['retention_rate'] for row in temporal_table],
                },
                {
                    'label': 'Taxa Nao Retencao (%)',
                    'data': [row['non_retention_rate'] for row in temporal_table],
                },
                {
                    'label': 'Taxa Call Drop (%)',
                    'data': [row['call_drop_rate'] for row in temporal_table],
                },
            ],
        },
        'churn_chart': {
            'labels': [row['churn_reason'] for row in top_reasons],
            'datasets': [
                {
                    'label': 'Total Chamadas',
                    'data': [row['total_calls'] for row in top_reasons],
                }
            ],
        },
        'actions_chart': {
            'labels': [row['retention_action'] for row in top_actions],
            'datasets': [
                {
                    'label': 'Taxa Sucesso (%)',
                    'data': [row['success_rate'] for row in top_actions],
                }
            ],
        },
        'chart_states': {
            'outcomes_chart': {
                'has_data': general_kpis['total_calls'] > 0,
                'empty_message': 'Sem dados suficientes para apresentar o grafico.',
            },
            'temporal_chart': {
                'has_data': any(row['total_calls'] > 0 for row in temporal_table),
                'empty_message': 'Sem dados suficientes para apresentar o grafico.',
            },
            'churn_chart': {
                'has_data': bool(top_reasons),
                'empty_message': 'Sem dados suficientes para apresentar o grafico.',
            },
            'actions_chart': {
                'has_data': bool(top_actions),
                'empty_message': 'Sem dados suficientes para apresentar o grafico.',
            },
        },
    }


def build_dashboard_payload(
    *,
    granularity='day',
    date_preset='current_month',
    assistant_name=None,
    assistant_id=None,
    start_date=None,
    end_date=None,
    service_type_id=None,
    churn_reason_id=None,
    retention_action_id=None,
    final_outcome_id=None,
):
    """Constroi todo o payload do dashboard sem logica nas views."""
    base_qs = selectors.get_inbound_queryset()
    base_qs = selectors.apply_filters(
        base_qs,
        assistant_name=assistant_name,
        assistant_id=assistant_id,
        start_date=start_date,
        end_date=end_date,
        service_type_id=service_type_id,
        churn_reason_id=churn_reason_id,
        retention_action_id=retention_action_id,
        final_outcome_id=final_outcome_id,
    )

    general_kpis = calculate_general_kpis(base_qs)
    churn_reason_table = build_churn_reason_table(base_qs)
    retention_action_table = build_retention_action_table(base_qs)
    service_type_table = build_service_type_table(base_qs)
    temporal_table = build_temporal_table(
        base_qs,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
    )
    monthly_rates_table = build_monthly_rates_table(
        base_qs,
        start_date=start_date,
        end_date=end_date,
    )
    daily_rates_table = build_daily_rates_table(
        base_qs,
        start_date=start_date,
        end_date=end_date,
    )
    assistant_ranking_table = build_assistant_ranking_table(base_qs)
    inconsistency_section = build_inconsistency_section(base_qs)
    tipification_tables = build_tipification_tables(base_qs)

    payload = {
        'general_kpis': general_kpis,
        'churn_reason_table': churn_reason_table,
        'retention_action_table': retention_action_table,
        'service_type_table': service_type_table,
        'temporal_table': temporal_table,
        'monthly_rates_table': monthly_rates_table,
        'daily_rates_table': daily_rates_table,
        'assistant_ranking_table': assistant_ranking_table,
        'inconsistency_section': inconsistency_section,
        'tipification_tables': tipification_tables,
        'frontend_payload': build_frontend_payload(
            general_kpis=general_kpis,
            temporal_table=temporal_table,
            churn_reason_table=churn_reason_table,
            retention_action_table=retention_action_table,
        ),
        'ui_state': _build_ui_state(general_kpis),
        'table_states': _build_table_states(
            churn_reason_table=churn_reason_table,
            retention_action_table=retention_action_table,
            service_type_table=service_type_table,
            monthly_rates_table=monthly_rates_table,
            assistant_ranking_table=assistant_ranking_table,
            inconsistency_section=inconsistency_section,
        ),
    }

    payload.update(
        _build_comparison_block(
            date_preset=date_preset,
            start_date=start_date,
            end_date=end_date,
            assistant_name=assistant_name,
            assistant_id=assistant_id,
            service_type_id=service_type_id,
            churn_reason_id=churn_reason_id,
            retention_action_id=retention_action_id,
            final_outcome_id=final_outcome_id,
            current_kpis=general_kpis,
        )
    )

    payload['service_type_comparison_table'] = _build_service_type_comparison_table(
        current_rows=service_type_table,
        previous_start=payload['comparison_context']['previous_start'],
        previous_end=payload['comparison_context']['previous_end'],
        assistant_name=assistant_name,
        assistant_id=assistant_id,
        service_type_id=service_type_id,
        churn_reason_id=churn_reason_id,
        retention_action_id=retention_action_id,
        final_outcome_id=final_outcome_id,
    )

    payload['churn_reason_comparison_table'] = _build_churn_reason_comparison_table(
        current_rows=churn_reason_table,
        previous_start=payload['comparison_context']['previous_start'],
        previous_end=payload['comparison_context']['previous_end'],
        assistant_name=assistant_name,
        assistant_id=assistant_id,
        service_type_id=service_type_id,
        churn_reason_id=churn_reason_id,
        retention_action_id=retention_action_id,
        final_outcome_id=final_outcome_id,
    )

    payload['retention_action_comparison_table'] = _build_retention_action_comparison_table(
        current_rows=retention_action_table,
        previous_start=payload['comparison_context']['previous_start'],
        previous_end=payload['comparison_context']['previous_end'],
        assistant_name=assistant_name,
        assistant_id=assistant_id,
        service_type_id=service_type_id,
        churn_reason_id=churn_reason_id,
        retention_action_id=retention_action_id,
        final_outcome_id=final_outcome_id,
    )

    payload['inconsistency_comparison_section'] = _build_inconsistency_comparison_section(
        current_section=inconsistency_section,
        previous_start=payload['comparison_context']['previous_start'],
        previous_end=payload['comparison_context']['previous_end'],
        assistant_name=assistant_name,
        assistant_id=assistant_id,
        service_type_id=service_type_id,
        churn_reason_id=churn_reason_id,
        retention_action_id=retention_action_id,
        final_outcome_id=final_outcome_id,
    )

    payload['assistant_comparison_table'] = _build_assistant_comparison_table(
        current_rows=assistant_ranking_table,
        previous_start=payload['comparison_context']['previous_start'],
        previous_end=payload['comparison_context']['previous_end'],
        assistant_name=assistant_name,
        assistant_id=assistant_id,
        service_type_id=service_type_id,
        churn_reason_id=churn_reason_id,
        retention_action_id=retention_action_id,
        final_outcome_id=final_outcome_id,
    )

    resolved_assistant_id = assistant_id or selectors.get_single_assistant_id(base_qs, assistant_name)
    if resolved_assistant_id:
        current_detail = build_assistant_detail(
            base_qs,
            resolved_assistant_id,
            granularity=granularity,
        )
        payload['assistant_detail'] = _build_assistant_detail_comparison(
            current_detail=current_detail,
            previous_start=payload['comparison_context']['previous_start'],
            previous_end=payload['comparison_context']['previous_end'],
            assistant_id=resolved_assistant_id,
            assistant_name=assistant_name,
            service_type_id=service_type_id,
            churn_reason_id=churn_reason_id,
            retention_action_id=retention_action_id,
            final_outcome_id=final_outcome_id,
            granularity=granularity,
        )

    return payload