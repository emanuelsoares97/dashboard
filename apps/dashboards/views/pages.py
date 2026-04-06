from django.shortcuts import get_object_or_404, render

from apps.dashboards.services import build_daily_rates_summary
from apps.dashboards.services import build_monthly_rates_summary
from apps.dashboards.services import generate_insights
from apps.inbound.models import Agent

from .helpers import _build_common_context
from .helpers import _build_dashboard_payload_from_filters
from .helpers import _resolve_filters


def overview(request):
    """Renderiza a pagina principal com KPIs, graficos e resumo executivo."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Visao Geral',
        active_section='overview',
        filters=filters,
        dashboard_payload=payload,
    )
    return render(request, 'dashboards/overview.html', context)


def churn_reasons(request):
    """Renderiza pagina dedicada aos motivos de churn."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Motivos de Corte',
        active_section='churn',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['churn_reason_comparison_table']
    return render(request, 'dashboards/churn_reasons.html', context)


def retention_actions(request):
    """Renderiza pagina dedicada as acoes de retencao."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Acoes de Retencao',
        active_section='actions',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['retention_action_comparison_table']
    return render(request, 'dashboards/retention_actions.html', context)


def services(request):
    """Renderiza pagina dedicada ao desempenho por servico."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Servicos',
        active_section='services',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['service_type_comparison_table']
    return render(request, 'dashboards/services.html', context)


def assistants(request):
    """Renderiza pagina de ranking geral de assistentes."""
    filters = _resolve_filters(request)
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Assistentes',
        active_section='assistants',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['assistant_comparison_table']
    return render(request, 'dashboards/assistants.html', context)


def assistant_detail(request, assistant_id):
    """Renderiza pagina individual de assistente com detalhe analitico."""
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


def inconsistencies(request):
    """Renderiza pagina dedicada a inconsistencias de tipificacao."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Inconsistencias',
        active_section='inconsistencies',
        filters=filters,
        dashboard_payload=payload,
    )
    context['section'] = payload['inconsistency_comparison_section']
    return render(request, 'dashboards/inconsistencies.html', context)


def insights(request):
    """Renderiza pagina dedicada a insights automaticos."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Insights Automaticos',
        active_section='insights',
        filters=filters,
        dashboard_payload=payload,
    )
    context['insights'] = generate_insights(filters)
    return render(request, 'dashboards/insights.html', context)


def monthly_rates(request):
    """Renderiza pagina com leitura mensal de retidos, nao retidos e call drop."""
    filters = _resolve_filters(request, force_assistant_name='')
    # Nesta aba, o objetivo e sempre ver historico mensal completo.
    payload = _build_dashboard_payload_from_filters(filters, use_filter_dates=False)

    context = _build_common_context(
        page_title='Taxas Mensais',
        active_section='monthly_rates',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['monthly_rates_table']
    context['summary'] = build_monthly_rates_summary(context['rows'])
    return render(request, 'dashboards/monthly_rates.html', context)


def daily_rates(request):
    """Renderiza pagina com leitura diaria de retidos, nao retidos e call drop."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)

    context = _build_common_context(
        page_title='Taxas Diarias',
        active_section='daily_rates',
        filters=filters,
        dashboard_payload=payload,
    )
    context['rows'] = payload['daily_rates_table']
    context['summary'] = build_daily_rates_summary(context['rows'])
    return render(request, 'dashboards/daily_rates.html', context)
