from django.urls import path

from apps.dashboards.views import agent_dashboard, team_dashboard

app_name = 'dashboards'

urlpatterns = [
    path('teams/', team_dashboard, name='team_dashboard'),
    path('agents/', agent_dashboard, name='agent_dashboard'),
]
