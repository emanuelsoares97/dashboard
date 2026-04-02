from django.db.models import Avg, Count, Q
from django.shortcuts import render

from apps.inbound.models import CallRecord
from apps.quality.models import TipificationInconsistency


def team_dashboard(request):
	rows = (
		CallRecord.objects.values('team_name')
		.annotate(
			total_calls=Count('id'),
			avg_duration_seconds=Avg('duration_seconds'),
			retained_calls=Count('id', filter=Q(ret_resolution__iexact='Retido', call_drop=False)),
		)
		.order_by('team_name')
	)

	context = {
		'rows': rows,
		'inconsistencies': TipificationInconsistency.objects.count(),
	}
	return render(request, 'dashboards/team_dashboard.html', context)


def agent_dashboard(request):
	team_filter = request.GET.get('team', '').strip()
	qs = CallRecord.objects.all()
	if team_filter:
		qs = qs.filter(team_name=team_filter)

	rows = (
		qs.values('team_name', 'agent_name')
		.annotate(
			total_calls=Count('id'),
			avg_duration_seconds=Avg('duration_seconds'),
		)
		.order_by('team_name', 'agent_name')
	)

	context = {
		'rows': rows,
		'team_filter': team_filter,
	}
	return render(request, 'dashboards/agent_dashboard.html', context)
