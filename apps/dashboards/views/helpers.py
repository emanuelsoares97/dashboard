from datetime import timedelta
from urllib.parse import urlencode

from django.utils.dateparse import parse_date

from apps.dashboards import selectors
from apps.dashboards.services import build_dashboard_payload


def _resolve_date_range(start_date_raw, end_date_raw, preset):
    """Resolve intervalo de datas por preset ou por selecao manual."""
    from django.utils import timezone

    today = timezone.localdate()

    if preset == 'today':
        return today, today

    if preset == 'last_7_days':
        return today - timedelta(days=6), today

    if preset == 'current_month':
        return today.replace(day=1), today

    if preset == 'previous_month':
        last_day_previous_month = today.replace(day=1) - timedelta(days=1)
        return last_day_previous_month.replace(day=1), last_day_previous_month

    start_date = parse_date(start_date_raw) if start_date_raw else None
    end_date = parse_date(end_date_raw) if end_date_raw else None
    return start_date, end_date


def _parse_optional_int(raw_value):
    """Converte valor de filtro opcional para inteiro, sem falhar para input invalido."""
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _resolve_filters(request, *, force_assistant_name=None):
    """Extrai e normaliza os filtros globais usados em todas as paginas."""
    granularity = request.GET.get('period', '').strip().lower()
    if granularity not in {'day', 'week', 'month'}:
        granularity = 'day'
    assistant_name = request.GET.get('assistant_name', '').strip()
    if force_assistant_name is not None:
        assistant_name = force_assistant_name

    date_preset = request.GET.get('date_preset', 'current_month').strip() or 'current_month'
    start_date_raw = request.GET.get('start_date', '').strip()
    end_date_raw = request.GET.get('end_date', '').strip()
    service_type_id_raw = request.GET.get('service_type_id', '').strip()
    churn_reason_id_raw = request.GET.get('churn_reason_id', '').strip()
    retention_action_id_raw = request.GET.get('retention_action_id', '').strip()
    final_outcome_id_raw = request.GET.get('final_outcome_id', '').strip()
    start_date, end_date = _resolve_date_range(start_date_raw, end_date_raw, date_preset)
    return {
        'period': granularity,
        'assistant_name': assistant_name,
        'date_preset': date_preset,
        'start_date_raw': start_date_raw,
        'end_date_raw': end_date_raw,
        'start_date': start_date,
        'end_date': end_date,
        'service_type_id_raw': service_type_id_raw,
        'churn_reason_id_raw': churn_reason_id_raw,
        'retention_action_id_raw': retention_action_id_raw,
        'final_outcome_id_raw': final_outcome_id_raw,
        'service_type_id': _parse_optional_int(service_type_id_raw),
        'churn_reason_id': _parse_optional_int(churn_reason_id_raw),
        'retention_action_id': _parse_optional_int(retention_action_id_raw),
        'final_outcome_id': _parse_optional_int(final_outcome_id_raw),
    }


def _build_filter_options(filters):
    """Calcula opcoes reais dos filtros globais para o periodo selecionado."""
    base_qs = selectors.get_inbound_queryset()
    base_qs = selectors.apply_filters(
        base_qs,
        assistant_name=filters['assistant_name'],
        start_date=filters['start_date'],
        end_date=filters['end_date'],
    )
    return selectors.select_global_filter_options(base_qs)


def _build_dashboard_payload_from_filters(filters, *, assistant_id=None, use_filter_dates=True):
    """Construcao unica do payload para manter as views finas e coerentes."""
    resolved_start_date = filters['start_date'] if use_filter_dates else None
    resolved_end_date = filters['end_date'] if use_filter_dates else None
    return build_dashboard_payload(
        granularity=filters['period'],
        date_preset=filters['date_preset'],
        assistant_name=filters['assistant_name'],
        assistant_id=assistant_id,
        start_date=resolved_start_date,
        end_date=resolved_end_date,
        service_type_id=filters['service_type_id'],
        churn_reason_id=filters['churn_reason_id'],
        retention_action_id=filters['retention_action_id'],
        final_outcome_id=filters['final_outcome_id'],
    )


def _build_common_context(*, page_title, active_section, filters, dashboard_payload):
    """Monta contexto comum para shell multipagina (topbar + sidebar)."""
    filter_options = _build_filter_options(filters)
    querystring = urlencode(
        {
            'period': filters['period'],
            'assistant_name': filters['assistant_name'],
            'date_preset': filters['date_preset'],
            'start_date': filters['start_date_raw'],
            'end_date': filters['end_date_raw'],
            'service_type_id': filters['service_type_id_raw'],
            'churn_reason_id': filters['churn_reason_id_raw'],
            'retention_action_id': filters['retention_action_id_raw'],
            'final_outcome_id': filters['final_outcome_id_raw'],
        }
    )
    querystring_without_assistant = urlencode(
        {
            'period': filters['period'],
            'assistant_name': '',
            'date_preset': filters['date_preset'],
            'start_date': filters['start_date_raw'],
            'end_date': filters['end_date_raw'],
            'service_type_id': filters['service_type_id_raw'],
            'churn_reason_id': filters['churn_reason_id_raw'],
            'retention_action_id': filters['retention_action_id_raw'],
            'final_outcome_id': filters['final_outcome_id_raw'],
        }
    )

    return {
        'dashboard': dashboard_payload,
        'page_title': page_title,
        'active_section': active_section,
        'dashboard_querystring': querystring,
        'dashboard_querystring_without_assistant': querystring_without_assistant,
        'period': filters['period'],
        'assistant_name': filters['assistant_name'],
        'date_preset': filters['date_preset'],
        'start_date': filters['start_date'].isoformat() if filters['start_date'] else '',
        'end_date': filters['end_date'].isoformat() if filters['end_date'] else '',
        'service_type_id': filters['service_type_id_raw'],
        'churn_reason_id': filters['churn_reason_id_raw'],
        'retention_action_id': filters['retention_action_id_raw'],
        'final_outcome_id': filters['final_outcome_id_raw'],
        'filter_options': filter_options,
    }
