from django.shortcuts import redirect
from django.urls import reverse


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
