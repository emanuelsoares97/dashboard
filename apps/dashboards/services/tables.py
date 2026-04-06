from datetime import timedelta

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
                'churn_reason_id': row.get('churn_reason_id'),
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
                'retention_action_id': row.get('retention_action_id'),
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


def build_daily_rates_table(queryset, start_date=None, end_date=None):
    """Gera tabela diaria com totais e taxas para leitura operacional."""
    rows = []
    aggregated = {}

    for row in selectors.select_temporal(queryset, granularity='day'):
        period = _normalize_period(row['period'])
        if period is None:
            continue
        aggregated[period] = {
            'total_calls': row['total_calls'] or 0,
            'total_retained': row['total_retained'] or 0,
            'total_call_drop': row['total_call_drop'] or 0,
        }

    period_keys = _iter_periods(start_date, end_date, 'day') if start_date and end_date else sorted(aggregated)

    for period in period_keys:
        totals = aggregated.get(period, {'total_calls': 0, 'total_retained': 0, 'total_call_drop': 0})
        total_calls = totals['total_calls']
        total_retained = totals['total_retained']
        total_call_drop = totals['total_call_drop']
        total_non_retained = _totals_with_non_retained(total_calls, total_retained, total_call_drop)

        rows.append(
            {
                'day': period.strftime('%Y-%m-%d'),
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


def build_daily_rates_summary(rows):
    """Resume dias com melhor e pior retencao para leitura rapida do periodo."""
    valid_rows = [row for row in rows if row.get('total_calls', 0) > 0]
    if not valid_rows:
        return {
            'days_with_data': 0,
            'best_day': None,
            'worst_day': None,
        }

    best_day = max(valid_rows, key=lambda row: (row['retention_rate'], row['total_calls'], row['day']))
    worst_day = min(valid_rows, key=lambda row: (row['retention_rate'], -row['total_calls'], row['day']))

    return {
        'days_with_data': len(valid_rows),
        'best_day': {
            'day': best_day['day'],
            'retention_rate': best_day['retention_rate'],
            'total_calls': best_day['total_calls'],
        },
        'worst_day': {
            'day': worst_day['day'],
            'retention_rate': worst_day['retention_rate'],
            'total_calls': worst_day['total_calls'],
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

    by_assistant_rates = [
        {
            'assistant_id': row['interaction__agent_id'],
            'assistant_name': row['interaction__agent__name'] or 'Sem assistente',
            'inconsistency_total': row['total_inconsistencies'],
            'inconsistency_rate': _pct(row['total_inconsistencies'], total_calls),
        }
        for row in selectors.select_inconsistency_by_assistant(queryset)
    ]

    return {
        'table': table_rows,
        'kpis': {
            'total_inconsistencies': total_inconsistencies,
            'global_inconsistency_rate': _pct(total_inconsistencies, total_calls),
            'by_assistant': by_assistant_rates,
        },
    }
