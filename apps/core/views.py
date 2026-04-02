from django.shortcuts import render


def home(request):
	"""Apresenta a pagina inicial com o enquadramento da fase 1 do sistema."""
	return render(request, 'core/home.html')
