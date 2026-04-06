from django.shortcuts import redirect
from django.urls import reverse


def home(request):
	"""Redireciona utilizadores autenticados ao dashboard e anonimos ao login."""
	if request.user.is_authenticated:
		return redirect(reverse('dashboards:overview'))
	return redirect(reverse('core:login'))
