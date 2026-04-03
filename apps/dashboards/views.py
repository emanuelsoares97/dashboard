from datetime import timedelta
from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from apps.dashboards import selectors
from apps.dashboards import exporters
from apps.dashboards.services import build_dashboard_payload, build_monthly_rates_summary, generate_insights
from apps.inbound.models import Agent


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
	context['rows'] = payload['churn_reason_table']
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
	context['rows'] = payload['retention_action_table']
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
	context['rows'] = payload['assistant_ranking_table']
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
	context['section'] = payload['inconsistency_section']
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


def team_dashboard(request):
	"""Mantem compatibilidade com rota antiga, redirecionando para a visao geral."""
	querystring = request.GET.urlencode()
	overview_url = reverse('dashboards:overview')
	if querystring:
		return redirect(f'{overview_url}?{querystring}')
	return redirect(overview_url)


def agent_dashboard(request):
	"""Mantem compatibilidade com rota antiga, redirecionando para assistentes."""
	querystring = request.GET.urlencode()
	assistants_url = reverse('dashboards:assistants')
	if querystring:
		return redirect(f'{assistants_url}?{querystring}')
	return redirect(assistants_url)
