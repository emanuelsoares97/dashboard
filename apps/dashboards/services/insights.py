from django.urls import reverse

from apps.dashboards import selectors
from apps.dashboards.services.insight_recommendations import enrich_insight
from apps.dashboards.services.label_normalization import build_normalized_set
from apps.dashboards.services.label_normalization import is_label_in
from apps.dashboards.services.label_normalization import normalize_label

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSIGHTS_MIN_TOTAL_CALLS = 5
INSIGHTS_MIN_REASON_CALLS = 5
INSIGHTS_MIN_SERVICE_CALLS = 5
INSIGHTS_MIN_SUBCATEGORY_CALLS = 5
INSIGHTS_MIN_RESOLUTION_CALLS = 3
INSIGHTS_MIN_ASSISTANT_CALLS = 3
INSIGHTS_MIN_INCONSISTENCY_CALLS = 5
INSIGHTS_REASON_NOT_INDICATED_THRESHOLD = 15.0

INSIGHTS_RETAINED_LABELS = {'retido'}
INSIGHTS_CALL_DROP_LABELS = {'call drop', 'calldrop'}
INSIGHTS_REASON_NOT_INDICATED_LABELS = {
    'motivo nao indicado',
    'motivo não indicado',
    'nao indicado',
    'não indicado',
}

INSIGHTS_NORMALIZED_RETAINED_LABELS = build_normalized_set(INSIGHTS_RETAINED_LABELS)
INSIGHTS_NORMALIZED_CALL_DROP_LABELS = build_normalized_set(INSIGHTS_CALL_DROP_LABELS)
INSIGHTS_NORMALIZED_REASON_NOT_INDICATED_LABELS = build_normalized_set(INSIGHTS_REASON_NOT_INDICATED_LABELS)

# ---------------------------------------------------------------------------
# Private utility helpers
# ---------------------------------------------------------------------------


def _round2(value):
    if value is None:
        return 0.0
    return round(float(value), 2)


def _pct(numerator, denominator):
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


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
        'summary': description,
        'description': description,
        'available': available,
        'warning': warning,
        'reason_unavailable': reason_unavailable,
    }
    if url:
        insight['url'] = url
    return insight


def _eligible_assistants(rows):
    """Filtra assistentes com volume minimo para comparacoes de desempenho."""
    return [row for row in rows if row.get('total_calls', 0) >= INSIGHTS_MIN_ASSISTANT_CALLS]


def _display_label(value, fallback):
    text = str(value or '').strip()
    if text:
        return text
    return fallback


def _is_retained(ret_resolution, final_status):
    return is_label_in(ret_resolution, INSIGHTS_NORMALIZED_RETAINED_LABELS) or is_label_in(
        final_status, INSIGHTS_NORMALIZED_RETAINED_LABELS
    )


def _is_call_drop(*, is_call_drop_flag, ret_resolution, final_status):
    if is_call_drop_flag:
        return True
    return is_label_in(ret_resolution, INSIGHTS_NORMALIZED_CALL_DROP_LABELS) or is_label_in(
        final_status, INSIGHTS_NORMALIZED_CALL_DROP_LABELS
    )


def _extract_resolution(row):
    metadata = row.get('metadata') or {}
    return _display_label(
        metadata.get('original_resolution') or row.get('retention_action__label'),
        'Sem resolucao',
    )


def _extract_ret_resolution(row):
    metadata = row.get('metadata') or {}
    return _display_label(
        metadata.get('original_ret_resolution') or row.get('final_outcome__label'),
        'Sem resultado',
    )


def _extract_final_status(row):
    metadata = row.get('metadata') or {}
    return _display_label(metadata.get('final_status') or row.get('final_outcome__label'), 'Sem status')


def _collect_interactions(queryset):
    rows = queryset.values(
        'churn_reason__label',
        'subcategory',
        'service_type__label',
        'retention_action__label',
        'final_outcome__label',
        'is_call_drop',
        'metadata',
    )

    interactions = []
    for row in rows:
        reason = _display_label(row.get('churn_reason__label'), 'Sem motivo')
        subcategory = _display_label(row.get('subcategory'), 'Sem subcategoria')
        service = _display_label(row.get('service_type__label'), 'Sem servico')
        resolution = _extract_resolution(row)
        ret_resolution = _extract_ret_resolution(row)
        final_status = _extract_final_status(row)

        interactions.append(
            {
                'third_category': reason,
                'subcategory': subcategory,
                'service_type': service,
                'resolution': resolution,
                'ret_resolution': ret_resolution,
                'final_status': final_status,
                'is_retained': _is_retained(ret_resolution, final_status),
                'is_call_drop': _is_call_drop(
                    is_call_drop_flag=bool(row.get('is_call_drop')),
                    ret_resolution=ret_resolution,
                    final_status=final_status,
                ),
            }
        )

    return interactions


def _build_group_stats(interactions, key):
    grouped = {}

    for row in interactions:
        label = _display_label(row.get(key), f'Sem {key}')
        bucket = grouped.setdefault(
            label,
            {
                'label': label,
                'total_calls': 0,
                'total_retained': 0,
                'total_call_drop': 0,
            },
        )
        bucket['total_calls'] += 1
        if row['is_retained']:
            bucket['total_retained'] += 1
        if row['is_call_drop']:
            bucket['total_call_drop'] += 1

    stats = []
    for bucket in grouped.values():
        non_retained = max(bucket['total_calls'] - bucket['total_retained'] - bucket['total_call_drop'], 0)
        stats.append(
            {
                **bucket,
                'total_non_retained': non_retained,
                'retention_rate': _pct(bucket['total_retained'], bucket['total_calls']),
                'non_retention_rate': _pct(non_retained, bucket['total_calls']),
            }
        )

    return sorted(stats, key=lambda item: (-item['total_calls'], item['label']))


def _unavailable(title, reason):
    return _build_insight(
        type_='info',
        title=title,
        value='Indisponivel',
        description='Nao foi possivel gerar este insight com os dados atuais.',
        available=False,
        reason_unavailable=reason,
    )


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def generate_insights(filters):
    """Gera insights automaticos para leitura executiva na visao geral."""
    from apps.dashboards.services import (  # noqa: PLC0415
        build_assistant_ranking_table,
        build_inconsistency_section,
        calculate_general_kpis,
    )

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
            enrich_insight(
                _build_insight(
                    type_='info',
                    title='Insight indisponivel',
                    value='Sem dados',
                    description='Nao foi possivel gerar este insight com os dados atuais.',
                    available=False,
                    reason_unavailable='Sem dados para os filtros selecionados.',
                )
            )
        ]

    if total_calls < INSIGHTS_MIN_TOTAL_CALLS:
        return [
            enrich_insight(
                _build_insight(
                    type_='warning',
                    title='Insight indisponivel',
                    value='Amostra reduzida',
                    description='Nao foi possivel gerar este insight com os dados atuais.',
                    available=False,
                    reason_unavailable='Volume total abaixo do minimo para conclusoes fiaveis.',
                )
            )
        ]

    interactions = _collect_interactions(filtered_qs)
    reason_stats = _build_group_stats(interactions, 'third_category')
    service_stats = _build_group_stats(interactions, 'service_type')
    subcategory_stats = _build_group_stats(interactions, 'subcategory')
    resolution_stats = _build_group_stats(interactions, 'resolution')

    reason_by_service = {}
    for row in interactions:
        reason_by_service.setdefault(row['service_type'], []).append(row)

    insights = []

    top_reason = reason_stats[0] if reason_stats else None
    if not top_reason:
        insights.append(_unavailable('Maior motivo de corte', 'Nao existem motivos de corte no periodo.'))
    else:
        insights.append(
            _build_insight(
                type_='info',
                title='Maior motivo de corte',
                value=top_reason['label'],
                description=f"{top_reason['total_calls']} chamadas no periodo analisado.",
            )
        )

    eligible_reason_rates = [row for row in reason_stats if row['total_calls'] >= INSIGHTS_MIN_REASON_CALLS]
    if not eligible_reason_rates:
        insights.append(
            _unavailable(
                'Motivo com menor taxa de retencao',
                f'Motivos com menos de {INSIGHTS_MIN_REASON_CALLS} chamadas no periodo.',
            )
        )
    else:
        worst_reason = min(eligible_reason_rates, key=lambda row: (row['retention_rate'], -row['total_calls'], row['label']))
        insights.append(
            _build_insight(
                type_='warning',
                title='Motivo com menor taxa de retencao',
                value=worst_reason['label'],
                description=(
                    f"Retencao de {_fmt_pct(worst_reason['retention_rate'])} "
                    f"em {worst_reason['total_calls']} chamadas."
                ),
            )
        )

    if not eligible_reason_rates:
        insights.append(
            _unavailable(
                'Motivo com maior taxa de retencao',
                f'Motivos com menos de {INSIGHTS_MIN_REASON_CALLS} chamadas no periodo.',
            )
        )
    else:
        best_reason = max(eligible_reason_rates, key=lambda row: (row['retention_rate'], row['total_calls'], row['label']))
        insights.append(
            _build_insight(
                type_='success',
                title='Motivo com maior taxa de retencao',
                value=best_reason['label'],
                description=(
                    f"Retencao de {_fmt_pct(best_reason['retention_rate'])} "
                    f"em {best_reason['total_calls']} chamadas."
                ),
            )
        )

    eligible_services = [row for row in service_stats if row['total_calls'] >= INSIGHTS_MIN_SERVICE_CALLS]
    if not eligible_services:
        insights.append(
            _unavailable(
                'Servico com maior nao retencao',
                f'Servicos com menos de {INSIGHTS_MIN_SERVICE_CALLS} chamadas no periodo.',
            )
        )
        worst_service = None
    else:
        worst_service = max(eligible_services, key=lambda row: (row['non_retention_rate'], row['total_calls'], row['label']))
        insights.append(
            _build_insight(
                type_='warning',
                title='Servico com maior nao retencao',
                value=worst_service['label'],
                description=f"Nao retencao de {_fmt_pct(worst_service['non_retention_rate'])}.",
            )
        )

    eligible_subcategories = [row for row in subcategory_stats if row['total_calls'] >= INSIGHTS_MIN_SUBCATEGORY_CALLS]
    if not eligible_subcategories:
        insights.append(
            _unavailable(
                'Subcategoria com maior nao retencao',
                f'Subcategorias com menos de {INSIGHTS_MIN_SUBCATEGORY_CALLS} chamadas no periodo.',
            )
        )
    else:
        worst_subcategory = max(
            eligible_subcategories,
            key=lambda row: (row['non_retention_rate'], row['total_calls'], row['label']),
        )
        insights.append(
            _build_insight(
                type_='warning',
                title='Subcategoria com maior nao retencao',
                value=worst_subcategory['label'],
                description=f"Nao retencao de {_fmt_pct(worst_subcategory['non_retention_rate'])}.",
            )
        )

    eligible_resolution = [row for row in resolution_stats if row['total_calls'] >= INSIGHTS_MIN_RESOLUTION_CALLS]
    if not eligible_resolution:
        insights.append(
            _unavailable(
                'Resolucao mais utilizada',
                f'Resolucoes com menos de {INSIGHTS_MIN_RESOLUTION_CALLS} chamadas no periodo.',
            )
        )
    else:
        top_resolution = max(eligible_resolution, key=lambda row: (row['total_calls'], row['label']))
        insights.append(
            _build_insight(
                type_='info',
                title='Resolucao mais utilizada',
                value=top_resolution['label'],
                description=f"{top_resolution['total_calls']} chamadas no periodo analisado.",
            )
        )

    retained_resolution_counter = {}
    for row in interactions:
        if row['is_retained']:
            retained_resolution_counter[row['resolution']] = retained_resolution_counter.get(row['resolution'], 0) + 1

    if not retained_resolution_counter:
        insights.append(
            _unavailable(
                'Forma de retencao mais frequente nos casos retidos',
                'Nao existem casos retidos no periodo para comparar resolucoes.',
            )
        )
    else:
        top_retained_resolution = max(
            retained_resolution_counter.items(),
            key=lambda item: (item[1], normalize_label(item[0])),
        )
        insights.append(
            _build_insight(
                type_='success',
                title='Forma de retencao mais frequente nos casos retidos',
                value=top_retained_resolution[0],
                description=f"{top_retained_resolution[1]} casos retidos no periodo analisado.",
            )
        )

    total_call_drop = sum(1 for row in interactions if row['is_call_drop'])
    call_drop_rate = _pct(total_call_drop, total_calls)
    insights.append(
        _build_insight(
            type_='info',
            title='Taxa de call drop',
            value=_fmt_pct(call_drop_rate),
            description=f"{total_call_drop} chamadas classificadas como call drop.",
        )
    )

    reason_not_indicated_calls = sum(
        row['total_calls']
        for row in reason_stats
        if is_label_in(row['label'], INSIGHTS_NORMALIZED_REASON_NOT_INDICATED_LABELS)
    )
    reason_not_indicated_rate = _pct(reason_not_indicated_calls, total_calls)
    if reason_not_indicated_rate > INSIGHTS_REASON_NOT_INDICATED_THRESHOLD:
        insights.append(
            _build_insight(
                type_='warning',
                title='Uso de Motivo Nao Indicado',
                value=_fmt_pct(reason_not_indicated_rate),
                description=f"{reason_not_indicated_calls} chamadas com motivo nao indicado (acima do limiar de {_fmt_pct(INSIGHTS_REASON_NOT_INDICATED_THRESHOLD)}).",
            )
        )
    else:
        insights.append(
            _build_insight(
                type_='info',
                title='Uso de Motivo Nao Indicado',
                value=_fmt_pct(reason_not_indicated_rate),
                description=f"{reason_not_indicated_calls} chamadas com motivo nao indicado (abaixo do limiar de {_fmt_pct(INSIGHTS_REASON_NOT_INDICATED_THRESHOLD)}).",
            )
        )

    assistant_rows = build_assistant_ranking_table(filtered_qs)
    eligible_assistants = _eligible_assistants(assistant_rows)

    if len(eligible_assistants) < 2:
        insights.append(
            _unavailable(
                'Assistente acima da media',
                'Sao necessarios pelo menos dois assistentes com volume minimo para comparar.',
            )
        )
        insights.append(
            _unavailable(
                'Assistente abaixo da media',
                'Sao necessarios pelo menos dois assistentes com volume minimo para comparar.',
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
                _unavailable(
                    'Assistente acima da media',
                    'Nao foi encontrado assistente acima da media elegivel.',
                )
            )

        assistants_below_avg = [row for row in eligible_assistants if row['retention_rate'] < average_rate]
        if assistants_below_avg:
            low_assistant = min(assistants_below_avg, key=lambda row: (row['retention_rate'], -row['total_calls']))
            insights.append(
                _build_insight(
                    type_='warning',
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
                _unavailable(
                    'Assistente abaixo da media',
                    'Nao foi encontrado assistente abaixo da media elegivel.',
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
    if (
        total_calls >= INSIGHTS_MIN_INCONSISTENCY_CALLS
        and top_inconsistency
        and (top_inconsistency.get('total_inconsistencies') or 0) > 0
    ):
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
    else:
        insights.append(
            _unavailable(
                'Assistente com mais inconsistencias',
                'Sem dados de inconsistencias suficientes para identificar assistente.',
            )
        )

    critical_reasons = [
        row['label']
        for row in eligible_reason_rates
        if row['retention_rate'] == 0.0
    ]
    if not critical_reasons:
        insights.append(
            _unavailable(
                'Motivos criticos sem retencao',
                f'Nao existem motivos com pelo menos {INSIGHTS_MIN_REASON_CALLS} chamadas e 0% retencao.',
            )
        )
    else:
        critical_reasons = sorted(critical_reasons, key=normalize_label)
        insights.append(
            _build_insight(
                type_='warning',
                title='Motivos criticos sem retencao',
                value=', '.join(critical_reasons),
                description=(
                    f"{len(critical_reasons)} motivo(s) com volume minimo e taxa de retencao de 0%."
                ),
            )
        )

    if not worst_service or worst_service['label'] not in reason_by_service:
        insights.append(
            _unavailable(
                'Motivo mais frequente no servico com maior nao retencao',
                'Nao foi possivel identificar servico elegivel para cruzamento.',
            )
        )
    else:
        reason_stats_inside_service = _build_group_stats(reason_by_service[worst_service['label']], 'third_category')
        dominant_reason = reason_stats_inside_service[0] if reason_stats_inside_service else None
        if not dominant_reason:
            insights.append(
                _unavailable(
                    'Motivo mais frequente no servico com maior nao retencao',
                    'Nao existem motivos no servico com maior nao retencao.',
                )
            )
        else:
            insights.append(
                _build_insight(
                    type_='info',
                    title='Motivo mais frequente no servico com maior nao retencao',
                    value=dominant_reason['label'],
                    description=(
                        f"Servico: {worst_service['label']} | "
                        f"{dominant_reason['total_calls']} chamadas no motivo mais frequente."
                    ),
                )
            )

    return [enrich_insight(insight) for insight in insights]
