from django.shortcuts import redirect
from django.urls import reverse

from apps.dashboards.permissions import require_dashboard_access


@require_dashboard_access
def team_dashboard(request):
    """Mantem compatibilidade com rota antiga, redirecionando para a visao geral."""
    querystring = request.GET.urlencode()
    overview_url = reverse('dashboards:overview')
    if querystring:
        return redirect(f'{overview_url}?{querystring}')
    return redirect(overview_url)


@require_dashboard_access
def agent_dashboard(request):
    """Mantem compatibilidade com rota antiga, redirecionando para assistentes."""
    querystring = request.GET.urlencode()
    assistants_url = reverse('dashboards:assistants')
    if querystring:
        return redirect(f'{assistants_url}?{querystring}')
    return redirect(assistants_url)
