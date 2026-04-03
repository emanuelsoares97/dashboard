import calendar
from datetime import date, timedelta

from django.urls import reverse

from apps.dashboards import selectors


LOW_SAMPLE_CALLS_THRESHOLD = 10
INSIGHTS_MIN_TOTAL_CALLS = 5
INSIGHTS_MIN_REASON_CALLS = 2
INSIGHTS_MIN_REASON_SHARE = 0.15
INSIGHTS_MIN_ACTION_USES = 2
INSIGHTS_MIN_ACTION_SHARE = 0.15
INSIGHTS_MIN_SERVICE_CALLS = 2
INSIGHTS_MIN_SERVICE_SHARE = 0.15
INSIGHTS_MIN_ASSISTANT_CALLS = 3
INSIGHTS_MIN_INCONSISTENCY_CALLS = 5


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


def _fmt_pct(value):
    return f'{_round2(value):.2f}%'


def _assistant_detail_url(assistant_id):
    return reverse('dashboards:assistant_detail', args=[assistant_id])


def _build_insight(*, type_, title, value, description, available=True, warning=False, reason_unavailable=None, url=None):
    """Cria estrutura padrao de insight com metadata de confiabilidade."""
    insight = {
        'type': type_,
        'title': title,
        'value': value,
        'description': description,
        'available': available,
        'warning': warning,
        'reason_unavailable': reason_unavailable,
    }
    if url:
        insight['url'] = url
    return insight


def _eligible_by_volume(rows, *, count_key, total_calls, min_calls, min_share):
    """Filtra linhas elegiveis com volume minimo absoluto e relativo."""
    if not rows or total_calls <= 0:
        return []
    return [
        row
        for row in rows
        if row.get(count_key, 0) >= min_calls and (row.get(count_key, 0) / total_calls) >= min_share
    ]


def _eligible_assistants(rows):
    """Filtra assistentes com volume minimo para comparacoes de desempenho."""
    return [row for row in rows if row.get('total_calls', 0) >= INSIGHTS_MIN_ASSISTANT_CALLS]


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


def _resolve_previous_period(*, start_date, end_date, date_preset):
    """Resolve o periodo anterior equivalente para comparacao automatica."""
    if not start_date or not end_date or start_date > end_date:
        return None, None

    if date_preset == 'current_month':
        window_days = (end_date - start_date).days + 1
        previous_month_last_day = start_date - timedelta(days=1)
        previous_month_start = previous_month_last_day.replace(day=1)
        previous_end = previous_month_start + timedelta(days=window_days - 1)
        if previous_end > previous_month_last_day:
            previous_end = previous_month_last_day
        return previous_month_start, previous_end

    if date_preset == 'previous_month':
        this_month_start = start_date.replace(day=1)
        previous_month_last_day = this_month_start - timedelta(days=1)
        previous_start = previous_month_last_day.replace(day=1)
        return previous_start, previous_month_last_day

    # Para intervalos custom que representam dias corridos de um mesmo mes
    # (ex.: 01-08), compara com os mesmos dias no mes anterior.
    if (
        date_preset == 'custom'
        and start_date.day == 1
        and start_date.year == end_date.year
        and start_date.month == end_date.month
    ):
        previous_month_last_day = start_date - timedelta(days=1)
        previous_start = previous_month_last_day.replace(day=1)
        last_day_prev_month = calendar.monthrange(previous_start.year, previous_start.month)[1]
        previous_end_day = min(end_date.day, last_day_prev_month)
        previous_end = previous_start.replace(day=previous_end_day)
        return previous_start, previous_end

    window_days = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=window_days - 1)
    return previous_start, previous_end


def _compute_delta(current_value, previous_value):
    """Calcula delta absoluto, percentual e direcao para um KPI."""
    current = float(current_value or 0)
    previous = float(previous_value or 0)
    delta = round(current - previous, 2)

    if previous == 0:
        delta_pct = None if current != 0 else 0.0
    else:
        delta_pct = round((delta / previous) * 100, 2)

    if abs(delta) < 0.01:
        direction = 'neutral'
    elif delta > 0:
        direction = 'up'
    else:
        direction = 'down'

    return {
        'current': round(current, 2),
        'previous': round(previous, 2),
        'delta': delta,
        'delta_pct': delta_pct,
        'direction': direction,
    }


def _build_comparison_block(
    *,
    date_preset,
    start_date,
    end_date,
    assistant_name,
    assistant_id,
    service_type_id,
    churn_reason_id,
    retention_action_id,
    final_outcome_id,
    current_kpis,
):
    """Constroi contexto e KPIs de comparacao com o periodo anterior."""
    previous_start, previous_end = _resolve_previous_period(
        start_date=start_date,
        end_date=end_date,
        date_preset=date_preset,
    )

    if not previous_start or not previous_end:
        return {
            'comparison_context': {
                'enabled': False,
                'current_start': start_date,
                'current_end': end_date,
                'previous_start': None,
                'previous_end': None,
            },
            'comparison_kpis': {},
        }

    previous_qs = selectors.get_inbound_queryset()
    previous_qs = selectors.apply_filters(
        previous_qs,
        assistant_name=assistant_name,
        assistant_id=assistant_id,
        start_date=previous_start,
        end_date=previous_end,
        service_type_id=service_type_id,
        churn_reason_id=churn_reason_id,
        retention_action_id=retention_action_id,
        final_outcome_id=final_outcome_id,
    )
    previous_kpis = calculate_general_kpis(previous_qs)

    return {
        'comparison_context': {
            'enabled': True,
            'current_start': start_date,
            'current_end': end_date,
            'previous_start': previous_start,
            'previous_end': previous_end,
        },
        'comparison_kpis': {
            'total_calls': _compute_delta(current_kpis['total_calls'], previous_kpis['total_calls']),
            'retention_rate': _compute_delta(current_kpis['retention_rate'], previous_kpis['retention_rate']),
            'non_retention_rate': _compute_delta(current_kpis['non_retention_rate'], previous_kpis['non_retention_rate']),
            'call_drop_rate': _compute_delta(current_kpis['call_drop_rate'], previous_kpis['call_drop_rate']),
            'avg_duration_seconds': _compute_delta(current_kpis['avg_duration_seconds'], previous_kpis['avg_duration_seconds']),
        },
    }


def get_status_class(value, avg):
    """Classifica visualmente uma taxa para leitura executiva."""
    if value is None:
        return 'badge-warning'

    numeric_value = float(value)
    if numeric_value >= 35:
        return 'badge-good'
    if numeric_value < 28:
        return 'badge-critical'
    return 'badge-warning'


def _apply_status_badges(rows, *, metric_key, status_key):
    """Aplica classe base e realca melhor/pior valor para leitura rapida."""
    if not rows:
        return rows

    values = [row.get(metric_key, 0) for row in rows]
    avg_value = sum(values) / len(values)
    max_value = max(values)
    min_value = min(values)

    for row in rows:
        value = row.get(metric_key, 0)
        status_class = get_status_class(value, avg_value)
        if len(rows) > 1 and value == max_value:
            status_class = 'badge-good'
        elif len(rows) > 1 and value == min_value:
            status_class = 'badge-critical'
        row[status_key] = status_class

    return rows


def _normalize_period(period):
    if period is None:
        return None
    if hasattr(period, 'date'):
        return period.date()
    return period


def _iter_periods(start_date, end_date, granularity):
    if not start_date or not end_date or start_date > end_date:
        return []

    if granularity == 'month':
        cursor = start_date.replace(day=1)
        end_marker = end_date.replace(day=1)
        periods = []
        while cursor <= end_marker:
            periods.append(cursor)
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1, day=1)
        return periods

    if granularity == 'week':
        cursor = start_date - timedelta(days=start_date.weekday())
        end_marker = end_date - timedelta(days=end_date.weekday())
        periods = []
        while cursor <= end_marker:
            periods.append(cursor)
            cursor += timedelta(days=7)
        return periods

    cursor = start_date
    periods = []
    while cursor <= end_date:
        periods.append(cursor)
        cursor += timedelta(days=1)
    return periods


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

    _apply_status_badges(rows, metric_key='retention_rate', status_key='retention_status_class')
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

    _apply_status_badges(rows, metric_key='success_rate', status_key='success_status_class')
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

    _apply_status_badges(rows, metric_key='retention_rate', status_key='retention_status_class')
    return rows


def build_temporal_table(queryset, granularity='day', start_date=None, end_date=None):
    """Gera serie temporal por dia/semana/mes para graficos e tabelas."""
    rows = []
    aggregated = {}

    for row in selectors.select_temporal(queryset, granularity=granularity):
        period = _normalize_period(row['period'])
        if period is None:
            continue
        aggregated[period] = {
            'total_calls': row['total_calls'] or 0,
            'total_retained': row['total_retained'] or 0,
            'total_call_drop': row['total_call_drop'] or 0,
        }

    period_keys = _iter_periods(start_date, end_date, granularity) if start_date and end_date else sorted(aggregated)

    for period in period_keys:
        totals = aggregated.get(period, {'total_calls': 0, 'total_retained': 0, 'total_call_drop': 0})
        total_calls = totals['total_calls']
        retained = totals['total_retained']
        call_drop = totals['total_call_drop']
        non_retained = _totals_with_non_retained(total_calls, retained, call_drop)

        rows.append(
            {
                'period': period.isoformat(),
                'total_calls': total_calls,
                'retention_rate': _pct(retained, total_calls),
                'non_retention_rate': _pct(non_retained, total_calls),
                'call_drop_rate': _pct(call_drop, total_calls),
            }
        )

    return rows


def build_monthly_rates_table(queryset, start_date=None, end_date=None):
    """Gera tabela mensal com totais e taxas para leitura operacional."""
    rows = []
    aggregated = {}

    for row in selectors.select_temporal(queryset, granularity='month'):
        period = _normalize_period(row['period'])
        if period is None:
            continue
        aggregated[period] = {
            'total_calls': row['total_calls'] or 0,
            'total_retained': row['total_retained'] or 0,
            'total_call_drop': row['total_call_drop'] or 0,
        }

    period_keys = _iter_periods(start_date, end_date, 'month') if start_date and end_date else sorted(aggregated)

    for period in period_keys:
        totals = aggregated.get(period, {'total_calls': 0, 'total_retained': 0, 'total_call_drop': 0})
        total_calls = totals['total_calls']
        total_retained = totals['total_retained']
        total_call_drop = totals['total_call_drop']
        total_non_retained = _totals_with_non_retained(total_calls, total_retained, total_call_drop)

        rows.append(
            {
                'month': period.strftime('%Y-%m'),
                'total_calls': total_calls,
                'total_retained': total_retained,
                'total_non_retained': total_non_retained,
                'total_call_drop': total_call_drop,
                'retention_rate': _pct(total_retained, total_calls),
                'non_retention_rate': _pct(total_non_retained, total_calls),
                'call_drop_rate': _pct(total_call_drop, total_calls),
            }
        )

    _apply_status_badges(rows, metric_key='retention_rate', status_key='retention_status_class')
    return rows


def build_monthly_rates_summary(rows):
    """Resume meses com melhor e pior retencao para leitura anual rapida."""
    valid_rows = [row for row in rows if row.get('total_calls', 0) > 0]
    if not valid_rows:
        return {
            'months_with_data': 0,
            'best_month': None,
            'worst_month': None,
        }

    best_month = max(valid_rows, key=lambda row: (row['retention_rate'], row['total_calls'], row['month']))
    worst_month = min(valid_rows, key=lambda row: (row['retention_rate'], -row['total_calls'], row['month']))

    return {
        'months_with_data': len(valid_rows),
        'best_month': {
            'month': best_month['month'],
            'retention_rate': best_month['retention_rate'],
            'total_calls': best_month['total_calls'],
        },
        'worst_month': {
            'month': worst_month['month'],
            'retention_rate': worst_month['retention_rate'],
            'total_calls': worst_month['total_calls'],
        },
    }


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

    _apply_status_badges(rows, metric_key='retention_rate', status_key='retention_status_class')
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


def generate_insights(filters):
    """Gera insights automaticos para leitura executiva na visao geral."""
    base_qs = selectors.get_inbound_queryset()
    filtered_qs = selectors.apply_filters(
        base_qs,
        assistant_name=filters.get('assistant_name'),
        start_date=filters.get('start_date'),
        end_date=filters.get('end_date'),
        service_type_id=filters.get('service_type_id'),
        churn_reason_id=filters.get('churn_reason_id'),
        retention_action_id=filters.get('retention_action_id'),
        final_outcome_id=filters.get('final_outcome_id'),
    )

    general_kpis = calculate_general_kpis(filtered_qs)
    total_calls = general_kpis['total_calls']

    if total_calls == 0:
        return [
            _build_insight(
                type_='info',
                title='Insight indisponivel',
                value='Sem dados',
                description='Nao foi possivel gerar este insight com os dados atuais.',
                available=False,
                reason_unavailable='Sem dados para os filtros selecionados.',
            )
        ]

    if total_calls < INSIGHTS_MIN_TOTAL_CALLS:
        return [
            _build_insight(
                type_='warning',
                title='Insight indisponivel',
                value='Amostra reduzida',
                description='Nao foi possivel gerar este insight com os dados atuais.',
                available=False,
                reason_unavailable='Volume total abaixo do minimo para conclusoes fiaveis.',
            )
        ]

    insights = []

    churn_rows = [row for row in build_churn_reason_table(filtered_qs, sort='retention_asc') if row['total_calls'] > 0]
    eligible_reasons = _eligible_by_volume(
        churn_rows,
        count_key='total_calls',
        total_calls=total_calls,
        min_calls=INSIGHTS_MIN_REASON_CALLS,
        min_share=INSIGHTS_MIN_REASON_SHARE,
    )
    if not eligible_reasons:
        insights.append(
            _build_insight(
                type_='info',
                title='Pior motivo de corte',
                value='Indisponivel',
                description='Nao foi possivel gerar este insight com os dados atuais.',
                available=False,
                reason_unavailable='Motivos sem representatividade minima no periodo.',
            )
        )
    else:
        worst_reason = min(eligible_reasons, key=lambda row: (row['retention_rate'], -row['total_calls']))
        reason_warning = len(eligible_reasons) < 2
        insights.append(
            _build_insight(
                type_='warning',
                title='Pior motivo de corte',
                value=worst_reason['churn_reason'],
                description=f"Retencao de {_fmt_pct(worst_reason['retention_rate'])} em {worst_reason['total_calls']} chamadas.",
                warning=reason_warning,
                reason_unavailable='Leitura com cautela por baixa concorrencia entre motivos.' if reason_warning else None,
            )
        )

    top_reason = selectors.select_top_churn_reason_by_volume(filtered_qs)
    if top_reason and eligible_reasons:
        top_reason_warning = len(eligible_reasons) < 2
        insights.append(
            _build_insight(
                type_='info',
                title='Motivo com maior volume',
                value=top_reason.get('churn_reason__label') or 'Sem motivo',
                description=f"{top_reason['total_calls']} chamadas no periodo analisado",
                warning=top_reason_warning,
                reason_unavailable='Leitura com cautela por baixa concorrencia entre motivos.' if top_reason_warning else None,
            )
        )

    best_actions = [row for row in build_retention_action_table(filtered_qs) if row['total_used'] > 0]
    eligible_actions = _eligible_by_volume(
        best_actions,
        count_key='total_used',
        total_calls=total_calls,
        min_calls=INSIGHTS_MIN_ACTION_USES,
        min_share=INSIGHTS_MIN_ACTION_SHARE,
    )
    if not eligible_actions:
        insights.append(
            _build_insight(
                type_='info',
                title='Melhor acao de retencao',
                value='Indisponivel',
                description='Nao foi possivel gerar este insight com os dados atuais.',
                available=False,
                reason_unavailable='Acoes com utilizacao insuficiente para comparacao.',
            )
        )
    else:
        best_action = max(eligible_actions, key=lambda row: (row['success_rate'], row['total_used']))
        action_warning = len(eligible_actions) < 2
        insights.append(
            _build_insight(
                type_='success',
                title='Melhor acao de retencao',
                value=best_action['retention_action'],
                description=f"Taxa de sucesso de {_fmt_pct(best_action['success_rate'])} em {best_action['total_used']} usos.",
                warning=action_warning,
                reason_unavailable='Leitura com cautela por baixa concorrencia entre acoes.' if action_warning else None,
            )
        )

    top_action = selectors.select_top_retention_action_by_volume(filtered_qs)
    if top_action and eligible_actions:
        top_action_warning = len(eligible_actions) < 2
        insights.append(
            _build_insight(
                type_='info',
                title='Acao mais utilizada',
                value=top_action.get('retention_action__label') or 'Sem acao',
                description=f"Aplicada em {top_action['total_used']} chamadas",
                warning=top_action_warning,
                reason_unavailable='Leitura com cautela por baixa concorrencia entre acoes.' if top_action_warning else None,
            )
        )

    service_rows = [row for row in build_service_type_table(filtered_qs) if row['total_calls'] > 0]
    eligible_services = _eligible_by_volume(
        service_rows,
        count_key='total_calls',
        total_calls=total_calls,
        min_calls=INSIGHTS_MIN_SERVICE_CALLS,
        min_share=INSIGHTS_MIN_SERVICE_SHARE,
    )
    if len(eligible_services) < 2:
        insights.append(
            _build_insight(
                type_='info',
                title='Servico com maior nao retencao',
                value='Indisponivel',
                description='Nao foi possivel gerar este insight com os dados atuais.',
                available=False,
                reason_unavailable='Sao necessarios pelo menos dois servicos com volume minimo para comparar.',
            )
        )
    else:
        worst_service = max(eligible_services, key=lambda row: (row['non_retention_rate'], row['total_calls']))
        insights.append(
            _build_insight(
                type_='warning',
                title='Servico com maior nao retencao',
                value=worst_service['service_type'],
                description=f"Nao retencao de {_fmt_pct(worst_service['non_retention_rate'])}.",
            )
        )

    assistant_rows = [row for row in build_assistant_ranking_table(filtered_qs) if row['total_calls'] > 0]
    eligible_assistants = _eligible_assistants(assistant_rows)

    if len(eligible_assistants) < 2:
        insights.append(
            _build_insight(
                type_='info',
                title='Assistente acima da media',
                value='Indisponivel',
                description='Nao foi possivel gerar este insight com os dados atuais.',
                available=False,
                reason_unavailable='Sao necessarios pelo menos dois assistentes com volume minimo para comparar.',
            )
        )
        insights.append(
            _build_insight(
                type_='info',
                title='Assistente abaixo da media',
                value='Indisponivel',
                description='Nao foi possivel gerar este insight com os dados atuais.',
                available=False,
                reason_unavailable='Sao necessarios pelo menos dois assistentes com volume minimo para comparar.',
            )
        )
    else:
        average_rate = _round2(sum(row['retention_rate'] for row in eligible_assistants) / len(eligible_assistants))

        assistants_above_avg = [row for row in eligible_assistants if row['retention_rate'] > average_rate]
        if assistants_above_avg:
            top_assistant = max(assistants_above_avg, key=lambda row: (row['retention_rate'], row['total_calls']))
            insights.append(
                _build_insight(
                    type_='success',
                    title='Assistente acima da media',
                    value=top_assistant['assistant_name'],
                    url=_assistant_detail_url(top_assistant['assistant_id']),
                    description=(
                        f"Retencao de {_fmt_pct(top_assistant['retention_rate'])} "
                        f"(media elegivel: {_fmt_pct(average_rate)})."
                    ),
                )
            )
        else:
            insights.append(
                _build_insight(
                    type_='info',
                    title='Assistente acima da media',
                    value='Indisponivel',
                    description='Nao foi possivel gerar este insight com os dados atuais.',
                    available=False,
                    reason_unavailable='Nao foi encontrado assistente acima da media elegivel.',
                )
            )

        assistants_below_avg = [row for row in eligible_assistants if row['retention_rate'] < average_rate]
        if assistants_below_avg:
            low_assistant = min(assistants_below_avg, key=lambda row: (row['retention_rate'], -row['total_calls']))
            insights.append(
                _build_insight(
                    type_='info',
                    title='Assistente abaixo da media',
                    value=low_assistant['assistant_name'],
                    url=_assistant_detail_url(low_assistant['assistant_id']),
                    description=(
                        f"Retencao de {_fmt_pct(low_assistant['retention_rate'])} "
                        f"(media elegivel: {_fmt_pct(average_rate)})."
                    ),
                )
            )
        else:
            insights.append(
                _build_insight(
                    type_='info',
                    title='Assistente abaixo da media',
                    value='Indisponivel',
                    description='Nao foi possivel gerar este insight com os dados atuais.',
                    available=False,
                    reason_unavailable='Nao foi encontrado assistente abaixo da media elegivel.',
                )
            )

    inconsistency_kpis = build_inconsistency_section(filtered_qs)['kpis']
    insights.append(
        _build_insight(
            type_='info',
            title='Total de inconsistencias',
            value=str(inconsistency_kpis['total_inconsistencies']),
            description=f"Taxa global de {_fmt_pct(inconsistency_kpis['global_inconsistency_rate'])}.",
        )
    )

    top_inconsistency = selectors.select_inconsistency_by_assistant(filtered_qs).first()
    if total_calls >= INSIGHTS_MIN_INCONSISTENCY_CALLS and top_inconsistency and (top_inconsistency.get('total_inconsistencies') or 0) > 0:
        total_inconsistencies = top_inconsistency['total_inconsistencies']
        inconsistency_rate = _pct(total_inconsistencies, general_kpis['total_calls'])
        insights.append(
            _build_insight(
                type_='warning',
                title='Assistente com mais inconsistencias',
                value=top_inconsistency.get('interaction__agent__name') or 'Sem assistente',
                description=f"{total_inconsistencies} inconsistencias ({_fmt_pct(inconsistency_rate)})",
            )
        )

    return insights


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

    resolved_assistant_id = assistant_id or selectors.get_single_assistant_id(base_qs, assistant_name)
    if resolved_assistant_id:
        payload['assistant_detail'] = build_assistant_detail(
            base_qs,
            resolved_assistant_id,
            granularity=granularity,
        )

    return payload
