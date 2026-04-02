from datetime import timedelta

from django.shortcuts import render
from django.utils.dateparse import parse_date

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


def team_dashboard(request):
	"""Renderiza o dashboard geral sem incluir analise por equipa."""
	granularity = request.GET.get('period', 'day')
	date_preset = request.GET.get('date_preset', 'custom').strip() or 'custom'
	start_date_raw = request.GET.get('start_date', '').strip()
	end_date_raw = request.GET.get('end_date', '').strip()
	start_date, end_date = _resolve_date_range(start_date_raw, end_date_raw, date_preset)

	payload = build_dashboard_payload(
		granularity=granularity,
		start_date=start_date,
		end_date=end_date,
	)

	# Mantemos chaves legadas para nao quebrar os templates atuais enquanto evoluem.
	context = {
		'rows': payload['churn_reason_table'],
		'inconsistencies': payload['inconsistency_section']['kpis']['total_inconsistencies'],
		'dashboard': payload,
		'period': granularity,
		'start_date': start_date.isoformat() if start_date else '',
		'end_date': end_date.isoformat() if end_date else '',
		'date_preset': date_preset,
	}
	return render(request, 'dashboards/team_dashboard.html', context)


def agent_dashboard(request):
	"""Renderiza o ranking e detalhe por assistente para comparacao de performance."""
	assistant_name = request.GET.get('assistant_name', '').strip()
	granularity = request.GET.get('period', 'day')
	date_preset = request.GET.get('date_preset', 'custom').strip() or 'custom'
	start_date_raw = request.GET.get('start_date', '').strip()
	end_date_raw = request.GET.get('end_date', '').strip()
	start_date, end_date = _resolve_date_range(start_date_raw, end_date_raw, date_preset)

	payload = build_dashboard_payload(
		granularity=granularity,
		assistant_name=assistant_name,
		start_date=start_date,
		end_date=end_date,
	)

	context = {
		'rows': payload['assistant_ranking_table'],
		'team_filter': '',
		'dashboard': payload,
		'assistant_name': assistant_name,
		'period': granularity,
		'start_date': start_date.isoformat() if start_date else '',
		'end_date': end_date.isoformat() if end_date else '',
		'date_preset': date_preset,
	}
	return render(request, 'dashboards/agent_dashboard.html', context)
