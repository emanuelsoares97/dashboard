from django.shortcuts import redirect
from django.urls import reverse


def home(request):
	"""Redireciona a entrada principal para a visao geral do dashboard."""
	return redirect(reverse('dashboards:overview'))
