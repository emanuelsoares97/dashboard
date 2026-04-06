from django.shortcuts import redirect, render
from django.urls import reverse

from apps.dashboards.permissions import get_linked_agent
from apps.dashboards.permissions import has_dashboard_access
from apps.dashboards.permissions import is_assistant


def home(request):
	"""Encaminha utilizadores para login, dashboard ou pagina de acesso pendente."""
	if not request.user.is_authenticated:
		return redirect(reverse('core:login'))

	if is_assistant(request.user):
		linked_agent = get_linked_agent(request.user)
		if linked_agent:
			return redirect(reverse('dashboards:assistant_detail', args=[linked_agent.id]))
		return render(request, 'core/no_dashboard_access.html', status=200)

	if has_dashboard_access(request.user):
		return redirect(reverse('dashboards:overview'))

	return render(request, 'core/no_dashboard_access.html', status=200)
