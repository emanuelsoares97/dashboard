from django.urls import path

from apps.dashboards.views import (
    agent_dashboard,
    assistant_detail,
    assistants,
    churn_reasons,
    inconsistencies,
    overview,
    retention_actions,
    services,
    team_dashboard,
)

app_name = 'dashboards'

urlpatterns = [
    path('', overview, name='index'),
    path('overview/', overview, name='overview'),
    path('churn-reasons/', churn_reasons, name='churn_reasons'),
    path('retention-actions/', retention_actions, name='retention_actions'),
    path('services/', services, name='services'),
    path('assistants/', assistants, name='assistants'),
    path('assistants/<int:assistant_id>/', assistant_detail, name='assistant_detail'),
    path('inconsistencies/', inconsistencies, name='inconsistencies'),
    path('teams/', team_dashboard, name='team_dashboard'),
    path('agents/', agent_dashboard, name='agent_dashboard'),
]
