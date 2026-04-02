from apps.dashboards import selectors


def _round2(value):
    if value is None:
        return 0.0
    return round(float(value), 2)


def _pct(numerator, denominator):
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _totals_with_non_retained(total_calls, total_retained, total_call_drop):
    total_non_retained = max(total_calls - total_retained - total_call_drop, 0)
    return total_non_retained


def _take_top(rows, key, limit=8):
    return sorted(rows, key=lambda item: item.get(key, 0), reverse=True)[:limit]


def calculate_general_kpis(queryset):
    """Calcula os KPIs gerais do dashboard com arredondamento a 2 casas."""
    raw = selectors.select_kpis_base(queryset)
    total_calls = raw['total_calls'] or 0
    total_retained = raw['total_retained'] or 0
    total_call_drop = raw['total_call_drop'] or 0
    total_non_retained = _totals_with_non_retained(total_calls, total_retained, total_call_drop)

    return {
        'total_calls': total_calls,
        'total_retained': total_retained,
        'total_non_retained': total_non_retained,
        'total_call_drop': total_call_drop,
        'retention_rate': _pct(total_retained, total_calls),
        'non_retention_rate': _pct(total_non_retained, total_calls),
        'call_drop_rate': _pct(total_call_drop, total_calls),
        'avg_duration_seconds': _round2(raw['avg_duration_seconds']),
    }


def build_churn_reason_table(queryset, sort='volume'):
    """Gera tabela por motivo de churn com percentagens prontas para frontend."""
    rows = []
    total_calls = queryset.count()

    for row in selectors.select_by_churn_reason(queryset):
        reason_calls = row['total_calls'] or 0
        retained = row['total_retained'] or 0
        call_drop = row['total_call_drop'] or 0
        non_retained = _totals_with_non_retained(reason_calls, retained, call_drop)

        rows.append(
            {
                'churn_reason': row['churn_reason__label'] or 'Sem motivo',
                'total_calls': reason_calls,
                'pct_total': _pct(reason_calls, total_calls),
                'total_retained': retained,
                'total_non_retained': non_retained,
                'total_call_drop': call_drop,
                'retention_rate': _pct(retained, reason_calls),
                'non_retention_rate': _pct(non_retained, reason_calls),
                'call_drop_rate': _pct(call_drop, reason_calls),
            }
        )

    if sort == 'retention_asc':
        rows.sort(key=lambda item: (item['retention_rate'], -item['total_calls']))
    else:
        rows.sort(key=lambda item: (-item['total_calls'], item['retention_rate']))

    return rows


def build_retention_action_table(queryset):
    """Gera tabela por acao de retencao e respetiva eficacia."""
    rows = []
    total_calls = queryset.count()

    for row in selectors.select_by_retention_action(queryset):
        used = row['total_used'] or 0
        retained = row['total_retained'] or 0
        call_drop = row['total_call_drop'] or 0
        non_retained = _totals_with_non_retained(used, retained, call_drop)

        rows.append(
            {
                'retention_action': row['retention_action__label'] or 'Sem acao',
                'total_used': used,
                'pct_total': _pct(used, total_calls),
                'total_retained': retained,
                'total_non_retained': non_retained,
                'success_rate': _pct(retained, used),
                'failure_rate': _pct(non_retained, used),
            }
        )

    return rows


def build_service_type_table(queryset):
    """Gera tabela de desempenho por tipo de servico."""
    rows = []
    total_all_calls = queryset.count()

    for row in selectors.select_by_service_type(queryset):
        total_calls = row['total_calls'] or 0
        retained = row['total_retained'] or 0
        call_drop = row['total_call_drop'] or 0
        non_retained = _totals_with_non_retained(total_calls, retained, call_drop)

        rows.append(
            {
                'service_type': row['service_type__label'] or 'Sem tipo de servico',
                'total_calls': total_calls,
                'pct_total': _pct(total_calls, total_all_calls),
                'retention_rate': _pct(retained, total_calls),
                'non_retention_rate': _pct(non_retained, total_calls),
                'call_drop_rate': _pct(call_drop, total_calls),
            }
        )

    return rows


def build_temporal_table(queryset, granularity='day'):
    """Gera serie temporal por dia/semana/mes para graficos e tabelas."""
    rows = []

    for row in selectors.select_temporal(queryset, granularity=granularity):
        total_calls = row['total_calls'] or 0
        retained = row['total_retained'] or 0
        call_drop = row['total_call_drop'] or 0
        non_retained = _totals_with_non_retained(total_calls, retained, call_drop)

        period = row['period']
        period_label = period.isoformat() if period else 'Sem periodo'

        rows.append(
            {
                'period': period_label,
                'total_calls': total_calls,
                'retention_rate': _pct(retained, total_calls),
                'non_retention_rate': _pct(non_retained, total_calls),
                'call_drop_rate': _pct(call_drop, total_calls),
            }
        )

    return rows


def build_assistant_ranking_table(queryset):
    """Gera ranking de assistentes com taxas e inconsistencias."""
    rows = []
    inconsistencies_by_agent = selectors.select_inconsistency_count_by_agent(queryset)

    for row in selectors.select_assistant_ranking_base(queryset):
        total_calls = row['total_calls'] or 0
        retained = row['total_retained'] or 0
        call_drop = row['total_call_drop'] or 0
        non_retained = _totals_with_non_retained(total_calls, retained, call_drop)
        inconsistencies = inconsistencies_by_agent.get(row['agent_id'], 0)

        rows.append(
            {
                'assistant_id': row['agent_id'],
                'assistant_name': row['agent__name'] or 'Sem assistente',
                'total_calls': total_calls,
                'avg_duration_seconds': _round2(row['avg_duration_seconds']),
                'total_retained': retained,
                'total_non_retained': non_retained,
                'retention_rate': _pct(retained, total_calls),
                'non_retention_rate': _pct(non_retained, total_calls),
                'call_drop_rate': _pct(call_drop, total_calls),
                'inconsistency_rate': _pct(inconsistencies, total_calls),
            }
        )

    return rows


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


def build_tipification_tables(queryset, limit=10):
    """Gera tabelas de tipificacoes com mais retidos e mais nao retidos."""
    rows = []
    total_calls = queryset.count()

    for row in selectors.select_tipification_breakdown(queryset):
        row_total_calls = row['total_calls'] or 0
        total_retained = row['total_retained'] or 0
        total_call_drop = row['total_call_drop'] or 0
        total_non_retained = _totals_with_non_retained(row_total_calls, total_retained, total_call_drop)

        churn_reason = row['churn_reason__label'] or 'Sem motivo'
        retention_action = row['retention_action__label'] or 'Sem acao'

        rows.append(
            {
                'tipification_label': f'{churn_reason} | {retention_action}',
                'churn_reason': churn_reason,
                'retention_action': retention_action,
                'total_calls': row_total_calls,
                'pct_total': _pct(row_total_calls, total_calls),
                'total_retained': total_retained,
                'total_non_retained': total_non_retained,
            }
        )

    non_retained = sorted(
        rows,
        key=lambda item: (-item['total_non_retained'], -item['total_calls'], item['tipification_label']),
    )[:limit]
    retained = sorted(
        rows,
        key=lambda item: (-item['total_retained'], -item['total_calls'], item['tipification_label']),
    )[:limit]

    return {
        'non_retained': non_retained,
        'retained': retained,
    }


def build_inconsistency_section(queryset):
    """Gera tabela e indicadores de inconsistencias de tipificacao."""
    table_rows = []
    base_rows = list(selectors.select_inconsistency_table(queryset))
    total_calls = queryset.count()

    for row in base_rows:
        table_rows.append(
            {
                'assistant_name': row['interaction__agent__name'] or 'Sem assistente',
                'churn_reason': row['interaction__churn_reason__label'] or 'Sem motivo',
                'retention_action': row['interaction__retention_action__label'] or 'Sem acao',
                'final_outcome': row['interaction__final_outcome__label'] or 'Sem resultado',
                'inconsistency_type': row['description'],
            }
        )

    total_inconsistencies = len(table_rows)

    by_assistant = {}
    for row in table_rows:
        assistant = row['assistant_name']
        by_assistant[assistant] = by_assistant.get(assistant, 0) + 1

    by_assistant_rates = [
        {
            'assistant_name': assistant,
            'inconsistency_total': total,
            'inconsistency_rate': _pct(total, total_calls),
        }
        for assistant, total in sorted(by_assistant.items(), key=lambda item: (-item[1], item[0]))
    ]

    return {
        'table': table_rows,
        'kpis': {
            'total_inconsistencies': total_inconsistencies,
            'global_inconsistency_rate': _pct(total_inconsistencies, total_calls),
            'by_assistant': by_assistant_rates,
        },
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
    }


def build_dashboard_payload(
    *,
    granularity='day',
    assistant_name=None,
    assistant_id=None,
    start_date=None,
    end_date=None,
):
    """Constroi todo o payload do dashboard sem logica nas views."""
    base_qs = selectors.get_inbound_queryset()
    base_qs = selectors.apply_filters(
        base_qs,
        assistant_name=assistant_name,
        assistant_id=assistant_id,
        start_date=start_date,
        end_date=end_date,
    )

    general_kpis = calculate_general_kpis(base_qs)
    churn_reason_table = build_churn_reason_table(base_qs)
    retention_action_table = build_retention_action_table(base_qs)
    service_type_table = build_service_type_table(base_qs)
    temporal_table = build_temporal_table(base_qs, granularity=granularity)
    assistant_ranking_table = build_assistant_ranking_table(base_qs)
    inconsistency_section = build_inconsistency_section(base_qs)
    tipification_tables = build_tipification_tables(base_qs)

    payload = {
        'general_kpis': general_kpis,
        'churn_reason_table': churn_reason_table,
        'retention_action_table': retention_action_table,
        'service_type_table': service_type_table,
        'temporal_table': temporal_table,
        'assistant_ranking_table': assistant_ranking_table,
        'inconsistency_section': inconsistency_section,
        'tipification_tables': tipification_tables,
        'frontend_payload': build_frontend_payload(
            general_kpis=general_kpis,
            temporal_table=temporal_table,
            churn_reason_table=churn_reason_table,
            retention_action_table=retention_action_table,
        ),
    }

    resolved_assistant_id = assistant_id or selectors.get_single_assistant_id(base_qs, assistant_name)
    if resolved_assistant_id:
        payload['assistant_detail'] = build_assistant_detail(
            base_qs,
            resolved_assistant_id,
            granularity=granularity,
        )

    return payload
