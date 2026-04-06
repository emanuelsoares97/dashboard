from django.shortcuts import redirect, render
from django.urls import reverse

from apps.dashboards.permissions import has_dashboard_access


def home(request):
	"""Encaminha utilizadores para login, dashboard ou pagina de acesso pendente."""
	if not request.user.is_authenticated:
		return redirect(reverse('core:login'))

	if has_dashboard_access(request.user):
		return redirect(reverse('dashboards:overview'))

	return render(request, 'core/no_dashboard_access.html', status=200)
