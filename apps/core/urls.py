from django.urls import path

from apps.core.auth_views import DashboardLoginView
from apps.core.auth_views import DashboardLogoutView
from apps.core.views import home

app_name = 'core'

urlpatterns = [
    path('', home, name='home'),
    path('login/', DashboardLoginView.as_view(), name='login'),
    path('logout/', DashboardLogoutView.as_view(), name='logout'),
]
