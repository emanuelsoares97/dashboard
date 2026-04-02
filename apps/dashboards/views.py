from datetime import timedelta
from urllib.parse import urlencode

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from apps.dashboards.services import build_dashboard_payload
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


def _resolve_filters(request, *, force_assistant_name=None):
	"""Extrai e normaliza os filtros globais usados em todas as paginas."""
	granularity = request.GET.get('period', 'day')
	assistant_name = request.GET.get('assistant_name', '').strip()
	if force_assistant_name is not None:
		assistant_name = force_assistant_name

	date_preset = request.GET.get('date_preset', 'custom').strip() or 'custom'
	start_date_raw = request.GET.get('start_date', '').strip()
	end_date_raw = request.GET.get('end_date', '').strip()
	start_date, end_date = _resolve_date_range(start_date_raw, end_date_raw, date_preset)
	return {
		'period': granularity,
		'assistant_name': assistant_name,
		'date_preset': date_preset,
		'start_date_raw': start_date_raw,
		'end_date_raw': end_date_raw,
		'start_date': start_date,
		'end_date': end_date,
	}


def _build_common_context(*, page_title, active_section, filters, dashboard_payload):
	"""Monta contexto comum para shell multipagina (topbar + sidebar)."""
	querystring = urlencode(
		{
			'period': filters['period'],
			'assistant_name': filters['assistant_name'],
			'date_preset': filters['date_preset'],
			'start_date': filters['start_date_raw'],
			'end_date': filters['end_date_raw'],
		}
	)
	querystring_without_assistant = urlencode(
		{
			'period': filters['period'],
			'assistant_name': '',
			'date_preset': filters['date_preset'],
			'start_date': filters['start_date_raw'],
			'end_date': filters['end_date_raw'],
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
	}


def overview(request):
	"""Renderiza a pagina principal com KPIs, graficos e resumo executivo."""
	filters = _resolve_filters(request, force_assistant_name='')
	payload = build_dashboard_payload(
		granularity=filters['period'],
		assistant_name=filters['assistant_name'],
		start_date=filters['start_date'],
		end_date=filters['end_date'],
	)

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
	payload = build_dashboard_payload(
		granularity=filters['period'],
		assistant_name=filters['assistant_name'],
		start_date=filters['start_date'],
		end_date=filters['end_date'],
	)

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
	payload = build_dashboard_payload(
		granularity=filters['period'],
		assistant_name=filters['assistant_name'],
		start_date=filters['start_date'],
		end_date=filters['end_date'],
	)

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
	payload = build_dashboard_payload(
		granularity=filters['period'],
		assistant_name=filters['assistant_name'],
		start_date=filters['start_date'],
		end_date=filters['end_date'],
	)

	context = _build_common_context(
		page_title='Servicos',
		active_section='services',
		filters=filters,
		dashboard_payload=payload,
	)
	context['rows'] = payload['service_type_table']
	return render(request, 'dashboards/services.html', context)


def assistants(request):
	"""Renderiza pagina de ranking geral de assistentes."""
	filters = _resolve_filters(request)
	payload = build_dashboard_payload(
		granularity=filters['period'],
		assistant_name=filters['assistant_name'],
		start_date=filters['start_date'],
		end_date=filters['end_date'],
	)

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
	payload = build_dashboard_payload(
		granularity=filters['period'],
		assistant_id=assistant.id,
		start_date=filters['start_date'],
		end_date=filters['end_date'],
	)

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
	payload = build_dashboard_payload(
		granularity=filters['period'],
		assistant_name=filters['assistant_name'],
		start_date=filters['start_date'],
		end_date=filters['end_date'],
	)

	context = _build_common_context(
		page_title='Inconsistencias',
		active_section='inconsistencies',
		filters=filters,
		dashboard_payload=payload,
	)
	context['section'] = payload['inconsistency_section']
	return render(request, 'dashboards/inconsistencies.html', context)


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
