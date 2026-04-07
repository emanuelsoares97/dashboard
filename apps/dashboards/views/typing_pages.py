from apps.dashboards.permissions import require_dashboard_access
from apps.dashboards.services.typing import build_typing_analysis_payload
from apps.dashboards import exporters

from django.shortcuts import render
from django.utils.dateparse import parse_date

from .helpers import _build_common_context, _build_filter_options, _resolve_filters


@require_dashboard_access
def typing_analysis(request):
    """Renderiza a página de análise de tipificações."""
    filters = _resolve_filters(request, force_assistant_name='')
    # Suporte a filtro de assistente sem forçar valor vazio
    assistant_name = request.GET.get('assistant_name', '').strip()
    if assistant_name:
        filters['assistant_name'] = assistant_name

    payload = build_typing_analysis_payload(filters)
    filter_options = _build_filter_options(filters)

    context = _build_common_context(
        page_title='Análise de Tipificações',
        active_section='typing_analysis',
        filters=filters,
        dashboard_payload={},
    )
    context['typing'] = payload
    context['filter_options'] = filter_options
    return render(request, 'dashboards/typing_analysis.html', context)


@require_dashboard_access
def typing_analysis_csv(request):
    """Exporta a tabela de análise de tipificações para CSV."""
    from apps.dashboards.permissions import require_report_exports

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
    return exporters.export_typing_analysis_csv(payload['table'], filters, day_filter=day_filter)
