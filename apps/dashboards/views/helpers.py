from datetime import timedelta
from urllib.parse import urlencode

from django.utils.dateparse import parse_date

from apps.dashboards import selectors
from apps.dashboards.services import build_dashboard_payload


MOBILE_SUBCATEGORY_FILTERS = (
    'CC RET Movel',
    'CC RET Cancelamento Movel',
)

FIXED_SUBCATEGORY_FILTERS = (
    'CC RET Cancelamento Fibra e Movel',
    'CC RET Fibra',
    'CC RET TV Fibra e Movel',
    'CC RET TV',
    'CC RET Cancelamento Fibra',
    'CC RET TV Fixo Fibra e Movel',
    'CC RET Fibra e Movel',
    'CC RET TV e Fixo',
    'CC RET Fixo',
)

MOBILE_ADJUSTED_EXCLUDED_ACTION = 'retido migracao pre pago'
OUTBOUND_SUBCATEGORY_FILTER = 'CC RET Outbound'
DEFAULT_EXCLUDED_SUBCATEGORY_FILTERS = (OUTBOUND_SUBCATEGORY_FILTER,)


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
        'subcategory_exact_values': None,
        'subcategory_exclude_values': DEFAULT_EXCLUDED_SUBCATEGORY_FILTERS,
    }


def _build_filter_options(filters):
    """Calcula opcoes reais dos filtros globais para o periodo selecionado."""
    base_qs = selectors.get_inbound_queryset()
    base_qs = selectors.apply_filters(
        base_qs,
        assistant_name=filters['assistant_name'],
        start_date=filters['start_date'],
        end_date=filters['end_date'],
        subcategory_exact_values=filters.get('subcategory_exact_values'),
        subcategory_exclude_values=filters.get('subcategory_exclude_values'),
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
        subcategory_exact_values=filters.get('subcategory_exact_values'),
        subcategory_exclude_values=filters.get('subcategory_exclude_values'),
    )


def _annotate_mobile_adjusted_metrics(payload):
    """Calcula taxa ajustada sem contabilizar Retido Migracao Pre Pago como retido.

    Denominador: general_kpis.total_calls (total real de chamadas, inclui pre-pago).
    Numerador: general_kpis.total_retained - retidos_pre_pago_da_tabela.

    Usar o denominador da tabela seria errado porque build_retention_action_table
    aplica _exclude_outcome_labels() internamente, excluindo chamadas cujo
    retention_action coincide com labels de OutcomeFinal (ex: 'Nao Retido').
    Essas chamadas sao maioritariamente nao-retidas e a sua exclusao inflaria
    artificialmente a taxa ajustada, podendo torna-la maior que a taxa geral.
    """
    rows = []
    pre_pago_retained = 0

    for row in payload.get('retention_action_table', []):
        used = row.get('total_used', 0) or 0
        retained = row.get('total_retained', 0) or 0
        action_label = str(row.get('retention_action', '')).strip().lower()
        is_excluded = action_label == MOBILE_ADJUSTED_EXCLUDED_ACTION

        if is_excluded:
            pre_pago_retained += retained

        adjusted_retained = 0 if is_excluded else retained
        adjusted_rate = round((adjusted_retained / used) * 100, 2) if used else 0.0

        rows.append(
            {
                **row,
                'adjusted_total_retained': adjusted_retained,
                'adjusted_success_rate': adjusted_rate,
            }
        )

    general_kpis = payload.get('general_kpis', {})
    total_calls = general_kpis.get('total_calls') or 0
    total_retained = general_kpis.get('total_retained') or 0
    adjusted_retained_global = max(total_retained - pre_pago_retained, 0)
    adjusted_global_rate = round((adjusted_retained_global / total_calls) * 100, 2) if total_calls else 0.0

    payload['retention_action_table'] = rows
    payload.setdefault('general_kpis', {})['retention_rate_adjusted_mobile'] = adjusted_global_rate
    return payload


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
