from apps.dashboards import exporters

from .helpers import _build_dashboard_payload_from_filters
from .helpers import _resolve_filters


def daily_rates_csv(request):
    """Exporta a tabela de taxas diarias para CSV com os filtros ativos."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)
    return exporters.export_daily_rates_csv(payload['daily_rates_table'], filters)


def assistants_csv(request):
    """Exporta a tabela de assistentes para CSV com os filtros ativos."""
    filters = _resolve_filters(request)
    payload = _build_dashboard_payload_from_filters(filters)
    return exporters.export_assistants_csv(payload['assistant_ranking_table'], filters)


def monthly_rates_csv(request):
    """Exporta a tabela de taxas mensais para CSV com os filtros ativos."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters, use_filter_dates=False)
    return exporters.export_monthly_rates_csv(payload['monthly_rates_table'], filters)


def services_csv(request):
    """Exporta a tabela de servicos para CSV com os filtros ativos."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)
    return exporters.export_services_csv(payload['service_type_table'], filters)


def inconsistencies_csv(request):
    """Exporta a tabela de inconsistencias para CSV com os filtros ativos."""
    filters = _resolve_filters(request, force_assistant_name='')
    payload = _build_dashboard_payload_from_filters(filters)
    return exporters.export_inconsistencies_csv(payload['inconsistency_section'], filters)
