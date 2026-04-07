from collections import defaultdict

from apps.dashboards.selectors.typing import get_typing_queryset
from apps.dashboards.typing_analysis.loader import load_tipification_definitions
from apps.dashboards.typing_analysis.validator import (
    STATUS_BLANK_TYPIFICATION,
    STATUS_CORRECT,
    STATUS_EMPTY,
    STATUS_INSUFFICIENT,
    STATUS_LABELS,
    STATUS_LIKELY_CORRECT,
    STATUS_LIKELY_INCORRECT,
    STATUS_NEEDS_REVIEW,
    validate,
)

_TABLE_LIMIT = 500


def build_typing_analysis_payload(filters: dict) -> dict:
    """Executa a validação de tipificações para todas as interações e devolve os resultados estruturados."""
    qs = get_typing_queryset(filters)
    interactions = list(qs[:_TABLE_LIMIT])

    definitions = load_tipification_definitions()

    rows = []
    kpi_counts: dict[str, int] = defaultdict(int)
    total_empty = 0
    total_with_obs = 0

    # (nome_agente, categoria) → {correct: int, total: int}
    segment_agg: dict[tuple[str, str], dict] = defaultdict(lambda: {'correct': 0, 'total': 0})

    for interaction in interactions:
        cat = interaction.category or ''
        sub = interaction.subcategory or ''
        third = interaction.churn_reason.label if interaction.churn_reason_id else ''
        obs = interaction.observations or ''
        agent_name = interaction.agent.name

        result = validate(obs, cat, sub, third, definitions=definitions)

        if result.status == STATUS_EMPTY:
            total_empty += 1
        else:
            total_with_obs += 1
            kpi_counts[result.status] += 1

            seg_key = (agent_name, cat or '—')
            segment_agg[seg_key]['total'] += 1
            if result.status in (STATUS_CORRECT, STATUS_LIKELY_CORRECT):
                segment_agg[seg_key]['correct'] += 1

        rows.append({
            'interaction_id': interaction.id,
            'assistant_name': agent_name,
            'occurred_on': interaction.occurred_on,
            'category': cat,
            'subcategory': sub,
            'third_category': third,
            'observations': obs,
            'status': result.status,
            'status_label': result.status_label,
            'status_css': result.status_css,
            'used_score': result.used_score,
            'best_score': result.best_score,
            'best_path': result.best_path,
            'delta': result.delta,
            'reason': result.reason,
            'suggestion': result.suggestion,
        })

    total = total_with_obs + total_empty
    correct_rate = _pct(
        kpi_counts[STATUS_CORRECT] + kpi_counts[STATUS_LIKELY_CORRECT],
        total_with_obs,
    )

    kpis = {
        'total_interactions': total,
        'total_with_observations': total_with_obs,
        'total_empty_observations': total_empty,
        'total_correct': kpi_counts[STATUS_CORRECT],
        'total_likely_correct': kpi_counts[STATUS_LIKELY_CORRECT],
        'total_needs_review': kpi_counts[STATUS_NEEDS_REVIEW],
        'total_likely_incorrect': kpi_counts[STATUS_LIKELY_INCORRECT],
        'total_insufficient': kpi_counts[STATUS_INSUFFICIENT],
        'total_blank_typification': kpi_counts[STATUS_BLANK_TYPIFICATION],
        'correctness_rate': correct_rate,
    }

    segment_table = _build_segment_table(segment_agg)

    return {
        'kpis': kpis,
        'table': rows,
        'segment_table': segment_table,
        'definitions_loaded': len(definitions),
        'is_limited': len(interactions) == _TABLE_LIMIT,
    }


def _pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, 1)


def _build_segment_table(
    segment_agg: dict[tuple[str, str], dict],
) -> list[dict]:
    rows = []
    for (agent_name, category), counts in segment_agg.items():
        total = counts['total']
        correct = counts['correct']
        rows.append({
            'assistant_name': agent_name,
            'category': category,
            'total': total,
            'correct': correct,
            'correctness_rate': _pct(correct, total),
        })
    return sorted(rows, key=lambda r: (-r['total'], r['assistant_name']))
