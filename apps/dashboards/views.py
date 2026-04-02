from django.db.models import Avg, Count, Q
from django.shortcuts import render

from apps.inbound.models import Interaction
from apps.quality.models import DataQualityFlag


def team_dashboard(request):
	rows = (
		Interaction.objects.values('team__name')
		.annotate(
			total_calls=Count('id'),
			avg_duration_seconds=Avg('duration_seconds'),
			retained_calls=Count(
				'id',
				filter=Q(final_outcome__code='retido', is_call_drop=False),
			),
		)
		.order_by('team__name')
	)

	context = {
		'rows': rows,
		'inconsistencies': DataQualityFlag.objects.filter(
			flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY
		).count(),
	}
	return render(request, 'dashboards/team_dashboard.html', context)


def agent_dashboard(request):
	team_filter = request.GET.get('team', '').strip()
	qs = Interaction.objects.all()
	if team_filter:
		qs = qs.filter(team__name=team_filter)

	rows = (
		qs.values('team__name', 'agent__name')
		.annotate(
			total_calls=Count('id'),
			avg_duration_seconds=Avg('duration_seconds'),
		)
		.order_by('team__name', 'agent__name')
	)

	context = {
		'rows': rows,
		'team_filter': team_filter,
	}
	return render(request, 'dashboards/agent_dashboard.html', context)
