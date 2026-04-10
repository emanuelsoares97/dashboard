from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.dashboards.services import build_daily_rates_summary
from apps.dashboards.services import build_monthly_rates_summary
from apps.dashboards.services import generate_insights
from apps.dashboards.services.previous_day import build_previous_day_payload
from apps.dashboards.services.previous_day_export import export_previous_day_excel
from apps.inbound.models import Agent

from apps.dashboards.permissions import get_linked_agent
from apps.dashboards.permissions import is_assistant
from apps.dashboards.permissions import require_dashboard_access
from apps.dashboards.permissions import require_sensitive_analytics

from .helpers import _build_common_context
from .helpers import _build_dashboard_payload_from_filters
from .helpers import _annotate_mobile_adjusted_metrics
from .helpers import FIXED_SUBCATEGORY_FILTERS
from .helpers import MOBILE_SUBCATEGORY_FILTERS
from .helpers import _resolve_filters


OVERVIEW_SEGMENTS = {
    'overview': {
        'page_title': 'Visao Geral',
        'subcategory_exact_values': None,
        'overview_tab': 'general',
    },
    'overview_mobile': {
        'page_title': 'Visao Geral | Movel',
        'subcategory_exact_values': MOBILE_SUBCATEGORY_FILTERS,
        'overview_tab': 'mobile',
    },
    'overview_fixed': {
        'page_title': 'Visao Geral | Fixo',
        'subcategory_exact_values': FIXED_SUBCATEGORY_FILTERS,
        'overview_tab': 'fixed',
    },
}


def _redirect_assistant_to_own_detail_if_needed(request):
    if not is_assistant(request.user):
        return None

    linked_agent = get_linked_agent(request.user)
    if not linked_agent:
        raise PermissionDenied

    return redirect(reverse('dashboards:assistant_detail', args=[linked_agent.id]))


@require_dashboard_access
def overview(request):
    """Renderiza a pagina principal com KPIs, graficos e resumo executivo."""
    return _render_overview_segment(request, active_section='overview')


@require_dashboard_access
def overview_mobile(request):
    """Renderiza a visao principal filtrada para a subcategoria Movel."""
    return _render_overview_segment(request, active_section='overview_mobile')


@require_dashboard_access
def overview_fixed(request):
    """Renderiza a visao principal filtrada para a subcategoria Fixo."""
    return _render_overview_segment(request, active_section='overview_fixed')


def _render_overview_segment(request, *, active_section):
    """Centraliza a renderizacao das abas Geral, Movel e Fixo."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    segment_config = OVERVIEW_SEGMENTS[active_section]
    filters = _resolve_filters(request, force_assistant_name='')
    filters['subcategory_exact_values'] = segment_config['subcategory_exact_values']
    payload = _build_dashboard_payload_from_filters(filters)
    if segment_config['overview_tab'] == 'mobile':
        payload = _annotate_mobile_adjusted_metrics(payload)

    context = _build_common_context(
        page_title=segment_config['page_title'],
        active_section=active_section,
        filters=filters,
        dashboard_payload=payload,
    )
    context['overview_tab'] = segment_config['overview_tab']
    context['is_mobile_overview'] = segment_config['overview_tab'] == 'mobile'
    return render(request, 'dashboards/overview.html', context)


@require_dashboard_access
def churn_reasons(request):
    """Renderiza pagina dedicada aos motivos de churn."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Motivos de Cancelamento',
        active_section='churn',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['churn_reason_comparison_table']
    return render(request, 'dashboards/churn_reasons.html', context)


@require_dashboard_access
def retention_actions(request):
    """Renderiza pagina dedicada as acoes de retencao."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Estrategias de Retencao',
        active_section='actions',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['retention_action_comparison_table']
    return render(request, 'dashboards/retention_actions.html', context)


@require_dashboard_access
def services(request):
    """Renderiza pagina dedicada ao desempenho por servico."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Performance por Servico',
        active_section='services',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['service_type_comparison_table']
    return render(request, 'dashboards/services.html', context)


@require_dashboard_access
def assistants(request):
    """Renderiza pagina de ranking geral de assistentes."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request)
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Performance por Assistente',
        active_section='assistants',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['assistant_comparison_table']
    return render(request, 'dashboards/assistants.html', context)


@require_dashboard_access
def assistant_detail(request, assistant_id):
    """Renderiza pagina individual de assistente com detalhe analitico."""
    if is_assistant(request.user):
        linked_agent = get_linked_agent(request.user)
        if not linked_agent:
            raise PermissionDenied
        if linked_agent.id != assistant_id:
            raise PermissionDenied

    assistant = get_object_or_404(Agent, id=assistant_id)
    filters = _resolve_filters(request, force_assistant_name=assistant.name)
    payload = _build_dashboard_payload_from_filters(filters, assistant_id=assistant.id)

    context = _build_common_context(
        page_title=f'Detalhe | {assistant.name}',
        active_section='assistants',
        filters=filters,
        dashboard_payload=payload,
    )
    context['assistant'] = {
        'id': assistant.id,
        'label': assistant.name,
    }
    context['detail'] = payload.get('assistant_detail')
    context['inconsistency_section'] = payload['inconsistency_section']
    return render(request, 'dashboards/assistant_detail.html', context)


@require_sensitive_analytics
def inconsistencies(request):
    """Renderiza pagina dedicada a inconsistencias de tipificacao."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Qualidade de Dados',
        active_section='inconsistencies',
        filters=filters,
        dashboard_payload=payload,
    )
    context['section'] = payload['inconsistency_comparison_section']
    return render(request, 'dashboards/inconsistencies.html', context)


@require_sensitive_analytics
def insights(request):
    """Renderiza pagina dedicada a insights automaticos."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Insights Executivos',
        active_section='insights',
        filters=filters,
        dashboard_payload=payload,
    )

    insight_mode = request.GET.get('insight_mode', 'all').strip().lower()
    if insight_mode not in {'all', 'attention'}:
        insight_mode = 'all'

    all_insights = generate_insights(filters)
    attention_insights = [
        insight
        for insight in all_insights
        if insight.get('suggested_actions') or insight.get('audit_recommendation')
    ]

    insights_data = all_insights
    if insight_mode == 'attention':
        insights_data = attention_insights

    context['insights'] = insights_data
    context['insight_mode'] = insight_mode
    context['insight_total_count'] = len(all_insights)
    context['insight_attention_count'] = len(attention_insights)
    context['insight_visible_count'] = len(insights_data)
    return render(request, 'dashboards/insights.html', context)


@require_sensitive_analytics
def previous_day(request):
    """Renderiza pagina operacional de leitura do dia anterior."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request, force_assistant_name='')
    today = timezone.localdate()
    has_explicit_range = bool(
        request.GET.get('start_date', '').strip() or request.GET.get('end_date', '').strip()
    )
    if has_explicit_range:
        selected_day = filters.get('end_date') or filters.get('start_date') or (today - timedelta(days=1))
    else:
        selected_day = today - timedelta(days=1)

    filters['date_preset'] = 'custom'
    filters['start_date'] = selected_day
    filters['end_date'] = selected_day
    filters['start_date_raw'] = selected_day.isoformat()
    filters['end_date_raw'] = selected_day.isoformat()

    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Operacao D-1',
        active_section='previous_day',
        filters=filters,
        dashboard_payload=payload,
    )
    context['previous_day'] = build_previous_day_payload(
        filters,
        reference_date=today,
        target_day=selected_day,
    )
    return render(request, 'dashboards/previous_day.html', context)


@require_sensitive_analytics
def previous_day_export(request):
    """Exporta relatório do dia anterior para Excel."""
    filters = _resolve_filters(request, force_assistant_name='')
    today = timezone.localdate()
    has_explicit_range = bool(
        request.GET.get('start_date', '').strip() or request.GET.get('end_date', '').strip()
    )
    if has_explicit_range:
        selected_day = filters.get('end_date') or filters.get('start_date') or (today - timedelta(days=1))
    else:
        selected_day = today - timedelta(days=1)
    
    filters['date_preset'] = 'custom'
    filters['start_date'] = selected_day
    filters['end_date'] = filters['start_date']
    filters['start_date_raw'] = filters['start_date'].isoformat()
    filters['end_date_raw'] = filters['end_date'].isoformat()
    
    payload = build_previous_day_payload(
        filters,
        reference_date=today,
        target_day=selected_day,
    )
    return export_previous_day_excel(payload, filters)


@require_dashboard_access
def monthly_rates(request):
    """Renderiza pagina com leitura mensal de retidos, nao retidos e call drop."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request, force_assistant_name='')
    # Nesta aba, o objetivo e sempre ver historico mensal completo.
    payload = _build_dashboard_payload_from_filters(filters, use_filter_dates=False)

    context = _build_common_context(
        page_title='Evolucao Mensal',
        active_section='monthly_rates',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['monthly_rates_table']
    context['summary'] = build_monthly_rates_summary(context['rows'])
    return render(request, 'dashboards/monthly_rates.html', context)


@require_dashboard_access
def daily_rates(request):
    """Renderiza pagina com leitura diaria de retidos, nao retidos e call drop."""
    assistant_redirect = _redirect_assistant_to_own_detail_if_needed(request)
    if assistant_redirect:
        return assistant_redirect

    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Evolucao Diaria',
        active_section='daily_rates',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['daily_rates_table']
    context['summary'] = build_daily_rates_summary(context['rows'])
    return render(request, 'dashboards/daily_rates.html', context)
