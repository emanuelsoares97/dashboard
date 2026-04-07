from apps.dashboards.permissions import require_dashboard_access, require_report_exports
from apps.dashboards.services.typing import build_typing_analysis_payload
from apps.dashboards.typing_analysis.validator import (
    STATUS_BLANK_TYPIFICATION,
    STATUS_CORRECT,
    STATUS_EMPTY,
    STATUS_INSUFFICIENT,
    STATUS_LIKELY_CORRECT,
    STATUS_LIKELY_INCORRECT,
    STATUS_NEEDS_REVIEW,
)
from apps.dashboards import exporters

from django.shortcuts import render
from django.utils.dateparse import parse_date

from .helpers import _build_common_context, _build_filter_options, _resolve_filters

_TYPING_STATUS_OPTIONS = (
    ('all', 'Todos os estados'),
    ('manual_review', 'Com duvida (revisao manual)'),
    (STATUS_BLANK_TYPIFICATION, 'Tipificacao em branco'),
    (STATUS_NEEDS_REVIEW, 'Requer revisao'),
    (STATUS_LIKELY_INCORRECT, 'Provavel incorreto'),
    (STATUS_INSUFFICIENT, 'Info. insuficiente'),
    (STATUS_EMPTY, 'Observacao vazia'),
    (STATUS_LIKELY_CORRECT, 'Provavel correto'),
    (STATUS_CORRECT, 'Correto'),
)


def _parse_selected_ids(request) -> set[int]:
    selected_ids = set()
    for raw_value in request.GET.getlist('selected_id'):
        try:
            selected_ids.add(int(raw_value))
        except (TypeError, ValueError):
            continue
    return selected_ids


def _resolve_typing_status_filter(request) -> str:
    requested = request.GET.get('typing_status', 'all').strip()
    valid_values = {value for value, _label in _TYPING_STATUS_OPTIONS}
    return requested if requested in valid_values else 'all'


def _filter_typing_rows(rows, *, typing_status: str, selected_ids: set[int] | None = None):
    manual_review_statuses = {
        STATUS_NEEDS_REVIEW,
        STATUS_LIKELY_INCORRECT,
        STATUS_INSUFFICIENT,
        STATUS_EMPTY,
        STATUS_BLANK_TYPIFICATION,
    }

    filtered = rows
    if typing_status == 'manual_review':
        filtered = [row for row in filtered if row['status'] in manual_review_statuses]
    elif typing_status != 'all':
        filtered = [row for row in filtered if row['status'] == typing_status]

    if selected_ids:
        filtered = [row for row in filtered if row['interaction_id'] in selected_ids]

    return filtered


@require_dashboard_access
def typing_analysis(request):
    """Renderiza a página de análise de tipificações."""
    filters = _resolve_filters(request, force_assistant_name='')
    # Suporte a filtro de assistente sem forçar valor vazio
    assistant_name = request.GET.get('assistant_name', '').strip()
    if assistant_name:
        filters['assistant_name'] = assistant_name

    payload = build_typing_analysis_payload(filters)
    typing_status = _resolve_typing_status_filter(request)
    payload['table'] = _filter_typing_rows(payload['table'], typing_status=typing_status)

    filter_options = _build_filter_options(filters)

    context = _build_common_context(
        page_title='Análise de Tipificações',
        active_section='typing_analysis',
        filters=filters,
        dashboard_payload={},
    )
    context['typing'] = payload
    context['filter_options'] = filter_options
    context['typing_status'] = typing_status
    context['typing_status_options'] = _TYPING_STATUS_OPTIONS
    return render(request, 'dashboards/typing_analysis.html', context)


@require_dashboard_access
@require_report_exports
def typing_analysis_excel(request):
    """Exporta a tabela de análise de tipificações para Excel."""
    filters = _resolve_filters(request, force_assistant_name='')
    assistant_name = request.GET.get('assistant_name', '').strip()
    if assistant_name:
        filters['assistant_name'] = assistant_name

    day_raw = request.GET.get('day', '').strip()
    day_filter = parse_date(day_raw) if day_raw else None
    if day_filter:
        filters['start_date'] = day_filter
        filters['end_date'] = day_filter

    payload = build_typing_analysis_payload(filters)
    typing_status = _resolve_typing_status_filter(request)
    selected_ids = _parse_selected_ids(request)
    filtered_rows = _filter_typing_rows(
        payload['table'],
        typing_status=typing_status,
        selected_ids=selected_ids,
    )

    return exporters.export_typing_analysis_excel(filtered_rows, filters, day_filter=day_filter)
