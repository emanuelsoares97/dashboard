import calendar
from datetime import timedelta

from apps.dashboards import selectors


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


def _apply_trend_tone_to_delta(delta_dict, metric_name):
    """
    Enriquece delta com trend_tone (semantica visual).

    Direction: matematica pura (up/down/neutral)
    Trend tone: interpretacao semantica (positive/negative/neutral)

    Para metricas "quanto menos melhor" (taxas de falha, inconsistencia, duracao):
    - trend_tone inverte a direcao para colorizacao correta.

    Para metricas "quanto mais melhor" (taxa de retencao, total chamadas):
    - trend_tone segue a direcao.
    """
    direction = delta_dict['direction']

    # Metricas onde UP eh bom
    positive_metrics = {'retention_rate', 'total_calls'}
    # Metricas onde UP eh mau
    negative_metrics = {
        'non_retention_rate', 'call_drop_rate', 'inconsistency_rate',
        'avg_duration_seconds'
    }

    if metric_name in positive_metrics:
        # UP -> positive, DOWN -> negative
        trend_tone = direction
    elif metric_name in negative_metrics:
        # Inverte: UP -> negative, DOWN -> positive
        if direction == 'up':
            trend_tone = 'down'
        elif direction == 'down':
            trend_tone = 'up'
        else:
            trend_tone = direction
    else:
        # Metrica desconhecida: usa direction como esta (seguro por defeito)
        trend_tone = direction

    delta_dict['trend_tone'] = trend_tone
    return delta_dict


def _compute_delta(current_value, previous_value, metric_name=None):
    """Calcula delta absoluto, percentual, direcao e trend_tone para um KPI."""
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

    result = {
        'current': round(current, 2),
        'previous': round(previous, 2),
        'delta': delta,
        'delta_pct': delta_pct,
        'direction': direction,
    }

    # Aplicar trend_tone se metric_name fornecido
    if metric_name:
        result = _apply_trend_tone_to_delta(result, metric_name)
    else:
        # Por defaut, trend_tone = direction (compatibilidade)
        result['trend_tone'] = direction

    return result


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
    from apps.dashboards.services import calculate_general_kpis  # noqa: PLC0415

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
            'total_calls': _compute_delta(current_kpis['total_calls'], previous_kpis['total_calls'], metric_name='total_calls'),
            'retention_rate': _compute_delta(current_kpis['retention_rate'], previous_kpis['retention_rate'], metric_name='retention_rate'),
            'non_retention_rate': _compute_delta(current_kpis['non_retention_rate'], previous_kpis['non_retention_rate'], metric_name='non_retention_rate'),
            'call_drop_rate': _compute_delta(current_kpis['call_drop_rate'], previous_kpis['call_drop_rate'], metric_name='call_drop_rate'),
            'avg_duration_seconds': _compute_delta(current_kpis['avg_duration_seconds'], previous_kpis['avg_duration_seconds'], metric_name='avg_duration_seconds'),
        },
    }


def _build_service_type_comparison_table(
    *,
    current_rows,
    previous_start,
    previous_end,
    assistant_name,
    assistant_id,
    service_type_id,
    churn_reason_id,
    retention_action_id,
    final_outcome_id,
):
    """Enriquece a tabela atual de servicos com comparacao ao periodo anterior."""
    from apps.dashboards.services import build_service_type_table  # noqa: PLC0415

    if not current_rows:
        return []

    if not previous_start or not previous_end:
        return [dict(row) for row in current_rows]

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
    previous_rows = build_service_type_table(previous_qs)
    previous_by_service = {row['service_type']: row for row in previous_rows}

    comparison_rows = []
    for row in current_rows:
        previous_row = previous_by_service.get(row['service_type'], {})

        total_calls_cmp = _compute_delta(row['total_calls'], previous_row.get('total_calls', 0), metric_name='total_calls')
        retention_cmp = _compute_delta(row['retention_rate'], previous_row.get('retention_rate', 0), metric_name='retention_rate')
        non_retention_cmp = _compute_delta(row['non_retention_rate'], previous_row.get('non_retention_rate', 0), metric_name='non_retention_rate')
        call_drop_cmp = _compute_delta(row['call_drop_rate'], previous_row.get('call_drop_rate', 0), metric_name='call_drop_rate')

        comparison_rows.append(
            {
                **row,
                'total_calls_previous': total_calls_cmp['previous'],
                'total_calls_delta': total_calls_cmp['delta'],
                'total_calls_delta_pct': total_calls_cmp['delta_pct'],
                'total_calls_direction': total_calls_cmp['direction'],
                'total_calls_trend_tone': total_calls_cmp['trend_tone'],
                'retention_rate_previous': retention_cmp['previous'],
                'retention_rate_delta_pp': retention_cmp['delta'],
                'retention_rate_direction': retention_cmp['direction'],
                'retention_rate_trend_tone': retention_cmp['trend_tone'],
                'non_retention_rate_previous': non_retention_cmp['previous'],
                'non_retention_rate_delta_pp': non_retention_cmp['delta'],
                'non_retention_rate_direction': non_retention_cmp['direction'],
                'non_retention_rate_trend_tone': non_retention_cmp['trend_tone'],
                'call_drop_rate_previous': call_drop_cmp['previous'],
                'call_drop_rate_delta_pp': call_drop_cmp['delta'],
                'call_drop_rate_direction': call_drop_cmp['direction'],
                'call_drop_rate_trend_tone': call_drop_cmp['trend_tone'],
            }
        )

    return comparison_rows


def _build_churn_reason_comparison_table(
    *,
    current_rows,
    previous_start,
    previous_end,
    assistant_name,
    assistant_id,
    service_type_id,
    churn_reason_id,
    retention_action_id,
    final_outcome_id,
):
    """Enriquece a tabela atual de motivos de corte com comparacao ao periodo anterior."""
    from apps.dashboards.services import build_churn_reason_table  # noqa: PLC0415

    if not current_rows:
        return []

    if not previous_start or not previous_end:
        return [dict(row) for row in current_rows]

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
    previous_rows = build_churn_reason_table(previous_qs)

    def _reason_key(row):
        reason_id = row.get('churn_reason_id')
        if reason_id is not None:
            return f'id:{reason_id}'
        return f"label:{row.get('churn_reason', '')}"

    previous_by_reason = {_reason_key(row): row for row in previous_rows}

    comparison_rows = []
    for row in current_rows:
        previous_row = previous_by_reason.get(_reason_key(row), {})

        total_calls_cmp = _compute_delta(row['total_calls'], previous_row.get('total_calls', 0), metric_name='total_calls')
        retention_cmp = _compute_delta(row['retention_rate'], previous_row.get('retention_rate', 0), metric_name='retention_rate')
        non_retention_cmp = _compute_delta(row['non_retention_rate'], previous_row.get('non_retention_rate', 0), metric_name='non_retention_rate')
        call_drop_cmp = _compute_delta(row['call_drop_rate'], previous_row.get('call_drop_rate', 0), metric_name='call_drop_rate')

        comparison_rows.append(
            {
                **row,
                'total_calls_previous': total_calls_cmp['previous'],
                'total_calls_delta': total_calls_cmp['delta'],
                'total_calls_delta_pct': total_calls_cmp['delta_pct'],
                'total_calls_direction': total_calls_cmp['direction'],
                'total_calls_trend_tone': total_calls_cmp['trend_tone'],
                'retention_rate_previous': retention_cmp['previous'],
                'retention_rate_delta_pp': retention_cmp['delta'],
                'retention_rate_direction': retention_cmp['direction'],
                'retention_rate_trend_tone': retention_cmp['trend_tone'],
                'non_retention_rate_previous': non_retention_cmp['previous'],
                'non_retention_rate_delta_pp': non_retention_cmp['delta'],
                'non_retention_rate_direction': non_retention_cmp['direction'],
                'non_retention_rate_trend_tone': non_retention_cmp['trend_tone'],
                'call_drop_rate_previous': call_drop_cmp['previous'],
                'call_drop_rate_delta_pp': call_drop_cmp['delta'],
                'call_drop_rate_direction': call_drop_cmp['direction'],
                'call_drop_rate_trend_tone': call_drop_cmp['trend_tone'],
            }
        )

    return comparison_rows


def _build_retention_action_comparison_table(
    *,
    current_rows,
    previous_start,
    previous_end,
    assistant_name,
    assistant_id,
    service_type_id,
    churn_reason_id,
    retention_action_id,
    final_outcome_id,
):
    """Enriquece a tabela atual de acoes de retencao com comparacao ao periodo anterior."""
    from apps.dashboards.services import build_retention_action_table  # noqa: PLC0415

    if not current_rows:
        return []

    if not previous_start or not previous_end:
        return [dict(row) for row in current_rows]

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
    previous_rows = build_retention_action_table(previous_qs)

    def _action_key(row):
        action_id = row.get('retention_action_id')
        if action_id is not None:
            return f'id:{action_id}'
        return f"label:{row.get('retention_action', '')}"

    previous_by_action = {_action_key(row): row for row in previous_rows}

    comparison_rows = []
    for row in current_rows:
        previous_row = previous_by_action.get(_action_key(row), {})

        total_used_cmp = _compute_delta(row['total_used'], previous_row.get('total_used', 0), metric_name='total_calls')
        success_cmp = _compute_delta(row['success_rate'], previous_row.get('success_rate', 0), metric_name='retention_rate')
        failure_cmp = _compute_delta(row['failure_rate'], previous_row.get('failure_rate', 0), metric_name='non_retention_rate')

        comparison_rows.append(
            {
                **row,
                'total_used_previous': total_used_cmp['previous'],
                'total_used_delta': total_used_cmp['delta'],
                'total_used_delta_pct': total_used_cmp['delta_pct'],
                'total_used_direction': total_used_cmp['direction'],
                'total_used_trend_tone': total_used_cmp['trend_tone'],
                'success_rate_previous': success_cmp['previous'],
                'success_rate_delta_pp': success_cmp['delta'],
                'success_rate_direction': success_cmp['direction'],
                'success_rate_trend_tone': success_cmp['trend_tone'],
                'failure_rate_previous': failure_cmp['previous'],
                'failure_rate_delta_pp': failure_cmp['delta'],
                'failure_rate_direction': failure_cmp['direction'],
                'failure_rate_trend_tone': failure_cmp['trend_tone'],
            }
        )

    return comparison_rows


def _build_assistant_comparison_table(
    *,
    current_rows,
    previous_start,
    previous_end,
    assistant_name,
    assistant_id,
    service_type_id,
    churn_reason_id,
    retention_action_id,
    final_outcome_id,
):
    """Enriquece a tabela atual de assistentes com comparacao ao periodo anterior."""
    from apps.dashboards.services import build_assistant_ranking_table  # noqa: PLC0415

    if not current_rows:
        return []

    if not previous_start or not previous_end:
        return [dict(row) for row in current_rows]

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
    previous_rows = build_assistant_ranking_table(previous_qs)
    previous_by_assistant_id = {row['assistant_id']: row for row in previous_rows}

    comparison_rows = []
    for row in current_rows:
        previous_row = previous_by_assistant_id.get(row['assistant_id'], {})

        total_calls_cmp = _compute_delta(row['total_calls'], previous_row.get('total_calls', 0), metric_name='total_calls')
        retention_cmp = _compute_delta(row['retention_rate'], previous_row.get('retention_rate', 0), metric_name='retention_rate')
        non_retention_cmp = _compute_delta(row['non_retention_rate'], previous_row.get('non_retention_rate', 0), metric_name='non_retention_rate')
        call_drop_cmp = _compute_delta(row['call_drop_rate'], previous_row.get('call_drop_rate', 0), metric_name='call_drop_rate')
        inconsistency_cmp = _compute_delta(row['inconsistency_rate'], previous_row.get('inconsistency_rate', 0), metric_name='inconsistency_rate')
        duration_cmp = _compute_delta(row['avg_duration_seconds'], previous_row.get('avg_duration_seconds', 0), metric_name='avg_duration_seconds')

        comparison_rows.append(
            {
                **row,
                'total_calls_previous': total_calls_cmp['previous'],
                'total_calls_delta': total_calls_cmp['delta'],
                'total_calls_delta_pct': total_calls_cmp['delta_pct'],
                'total_calls_direction': total_calls_cmp['direction'],
                'total_calls_trend_tone': total_calls_cmp['trend_tone'],
                'retention_rate_previous': retention_cmp['previous'],
                'retention_rate_delta_pp': retention_cmp['delta'],
                'retention_rate_direction': retention_cmp['direction'],
                'retention_rate_trend_tone': retention_cmp['trend_tone'],
                'non_retention_rate_previous': non_retention_cmp['previous'],
                'non_retention_rate_delta_pp': non_retention_cmp['delta'],
                'non_retention_rate_direction': non_retention_cmp['direction'],
                'non_retention_rate_trend_tone': non_retention_cmp['trend_tone'],
                'call_drop_rate_previous': call_drop_cmp['previous'],
                'call_drop_rate_delta_pp': call_drop_cmp['delta'],
                'call_drop_rate_direction': call_drop_cmp['direction'],
                'call_drop_rate_trend_tone': call_drop_cmp['trend_tone'],
                'inconsistency_rate_previous': inconsistency_cmp['previous'],
                'inconsistency_rate_delta_pp': inconsistency_cmp['delta'],
                'inconsistency_rate_direction': inconsistency_cmp['direction'],
                'inconsistency_rate_trend_tone': inconsistency_cmp['trend_tone'],
                'avg_duration_seconds_previous': duration_cmp['previous'],
                'avg_duration_seconds_delta': duration_cmp['delta'],
                'avg_duration_seconds_direction': duration_cmp['direction'],
                'avg_duration_seconds_trend_tone': duration_cmp['trend_tone'],
            }
        )

    return comparison_rows


def _build_inconsistency_comparison_section(
    *,
    current_section,
    previous_start,
    previous_end,
    assistant_name,
    assistant_id,
    service_type_id,
    churn_reason_id,
    retention_action_id,
    final_outcome_id,
):
    """Enriquece a secao de inconsistencias com comparacao ao periodo anterior."""
    from apps.dashboards.services import build_inconsistency_section  # noqa: PLC0415

    if not previous_start or not previous_end:
        return current_section

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
    previous_section = build_inconsistency_section(previous_qs)

    total_cmp = _compute_delta(
        current_section['kpis']['total_inconsistencies'],
        previous_section['kpis']['total_inconsistencies'],
        metric_name='total_calls',
    )
    global_rate_cmp = _compute_delta(
        current_section['kpis']['global_inconsistency_rate'],
        previous_section['kpis']['global_inconsistency_rate'],
        metric_name='inconsistency_rate',
    )

    previous_by_assistant = {
        row['assistant_id']: row for row in previous_section['kpis']['by_assistant']
    }

    by_assistant_rows = []
    for row in current_section['kpis']['by_assistant']:
        previous_row = previous_by_assistant.get(row['assistant_id'], {})
        total_assistant_cmp = _compute_delta(
            row['inconsistency_total'],
            previous_row.get('inconsistency_total', 0),
            metric_name='total_calls',
        )
        rate_assistant_cmp = _compute_delta(
            row['inconsistency_rate'],
            previous_row.get('inconsistency_rate', 0),
            metric_name='inconsistency_rate',
        )
        by_assistant_rows.append(
            {
                **row,
                'inconsistency_total_previous': total_assistant_cmp['previous'],
                'inconsistency_total_delta': total_assistant_cmp['delta'],
                'inconsistency_total_delta_pct': total_assistant_cmp['delta_pct'],
                'inconsistency_total_direction': total_assistant_cmp['direction'],
                'inconsistency_rate_previous': rate_assistant_cmp['previous'],
                'inconsistency_rate_delta_pp': rate_assistant_cmp['delta'],
                'inconsistency_rate_direction': rate_assistant_cmp['direction'],
            }
        )

    return {
        **current_section,
        'kpis': {
            **current_section['kpis'],
            'total_inconsistencies_previous': total_cmp['previous'],
            'total_inconsistencies_delta': total_cmp['delta'],
            'total_inconsistencies_delta_pct': total_cmp['delta_pct'],
            'total_inconsistencies_direction': total_cmp['direction'],
            'global_inconsistency_rate_previous': global_rate_cmp['previous'],
            'global_inconsistency_rate_delta_pp': global_rate_cmp['delta'],
            'global_inconsistency_rate_direction': global_rate_cmp['direction'],
            'by_assistant': by_assistant_rows,
        },
    }


def _build_assistant_detail_comparison(
    *,
    current_detail,
    previous_start,
    previous_end,
    assistant_id,
    assistant_name,
    service_type_id,
    churn_reason_id,
    retention_action_id,
    final_outcome_id,
    granularity,
):
    """Enriquece o detalhe do assistente com comparacao ao periodo anterior."""
    from apps.dashboards.services import build_assistant_detail  # noqa: PLC0415

    if not previous_start or not previous_end:
        return current_detail

    previous_qs = selectors.get_inbound_queryset()
    previous_qs = selectors.apply_filters(
        previous_qs,
        assistant_id=assistant_id,
        assistant_name=assistant_name,
        start_date=previous_start,
        end_date=previous_end,
        service_type_id=service_type_id,
        churn_reason_id=churn_reason_id,
        retention_action_id=retention_action_id,
        final_outcome_id=final_outcome_id,
    )
    previous_detail = build_assistant_detail(previous_qs, assistant_id, granularity=granularity)
    prev_kpis = previous_detail['kpis']
    curr_kpis = current_detail['kpis']

    total_calls_cmp = _compute_delta(curr_kpis['total_calls'], prev_kpis['total_calls'], metric_name='total_calls')
    retention_cmp = _compute_delta(curr_kpis['retention_rate'], prev_kpis['retention_rate'], metric_name='retention_rate')
    non_retention_cmp = _compute_delta(curr_kpis['non_retention_rate'], prev_kpis['non_retention_rate'], metric_name='non_retention_rate')
    call_drop_cmp = _compute_delta(curr_kpis['call_drop_rate'], prev_kpis['call_drop_rate'], metric_name='call_drop_rate')
    duration_cmp = _compute_delta(curr_kpis['avg_duration_seconds'], prev_kpis['avg_duration_seconds'], metric_name='avg_duration_seconds')

    return {
        **current_detail,
        'kpis': {
            **curr_kpis,
            'total_calls_previous': total_calls_cmp['previous'],
            'total_calls_delta': total_calls_cmp['delta'],
            'total_calls_delta_pct': total_calls_cmp['delta_pct'],
            'total_calls_direction': total_calls_cmp['direction'],
            'retention_rate_previous': retention_cmp['previous'],
            'retention_rate_delta_pp': retention_cmp['delta'],
            'retention_rate_direction': retention_cmp['direction'],
            'non_retention_rate_previous': non_retention_cmp['previous'],
            'non_retention_rate_delta_pp': non_retention_cmp['delta'],
            'non_retention_rate_direction': non_retention_cmp['direction'],
            'call_drop_rate_previous': call_drop_cmp['previous'],
            'call_drop_rate_delta_pp': call_drop_cmp['delta'],
            'call_drop_rate_direction': call_drop_cmp['direction'],
            'avg_duration_seconds_previous': duration_cmp['previous'],
            'avg_duration_seconds_delta': duration_cmp['delta'],
            'avg_duration_seconds_delta_pct': duration_cmp['delta_pct'],
            'avg_duration_seconds_direction': duration_cmp['direction'],
        },
    }
