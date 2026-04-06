from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url


GROUP_ASSISTANTS = 'Assistentes'
GROUP_SUPERVISORS = 'Supervisores'
GROUP_COORDINATION = 'Coordenacao'

DASHBOARD_ACCESS_GROUPS = (
    GROUP_ASSISTANTS,
    GROUP_SUPERVISORS,
    GROUP_COORDINATION,
)

SENSITIVE_ANALYTICS_GROUPS = (
    GROUP_SUPERVISORS,
    GROUP_COORDINATION,
)

DASHBOARD_MANAGEMENT_GROUPS = (
    GROUP_COORDINATION,
)


def _is_in_any_group(user, group_names):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=group_names).exists()


def has_dashboard_access(user):
    return _is_in_any_group(user, DASHBOARD_ACCESS_GROUPS)


def can_view_sensitive_analytics(user):
    return _is_in_any_group(user, SENSITIVE_ANALYTICS_GROUPS)


def can_export_reports(user):
    return can_view_sensitive_analytics(user)


def can_manage_dashboard(user):
    return _is_in_any_group(user, DASHBOARD_MANAGEMENT_GROUPS)


def _permission_required(rule):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(
                    request.get_full_path(),
                    login_url=resolve_url(settings.LOGIN_URL),
                )
            if not rule(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


require_dashboard_access = _permission_required(has_dashboard_access)
require_sensitive_analytics = _permission_required(can_view_sensitive_analytics)
require_report_exports = _permission_required(can_export_reports)
require_dashboard_management = _permission_required(can_manage_dashboard)