from django.urls import reverse

from apps.dashboards import selectors

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSIGHTS_MIN_TOTAL_CALLS = 5
INSIGHTS_MIN_REASON_CALLS = 2
INSIGHTS_MIN_REASON_SHARE = 0.15
INSIGHTS_MIN_ACTION_USES = 2
INSIGHTS_MIN_ACTION_SHARE = 0.15
INSIGHTS_MIN_SERVICE_CALLS = 2
INSIGHTS_MIN_SERVICE_SHARE = 0.15
INSIGHTS_MIN_ASSISTANT_CALLS = 3
INSIGHTS_MIN_INCONSISTENCY_CALLS = 5

# ---------------------------------------------------------------------------
# Private utility helpers (self-contained copies; will consolidate to
# services/utils.py in Block 2 of the structural refactoring)
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


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def generate_insights(filters):
    """Gera insights automaticos para leitura executiva na visao geral."""
    # Late import to avoid circular dependency: services/__init__.py imports
    # this module, so we must not import from services at module level here.
    from apps.dashboards.services import (  # noqa: PLC0415
        build_assistant_ranking_table,
        build_churn_reason_table,
        build_inconsistency_section,
        build_retention_action_table,
        build_service_type_table,
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
