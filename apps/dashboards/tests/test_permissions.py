from django.contrib.auth.models import Group
from django.core.management import call_command

from apps.dashboards.permissions import GROUP_ASSISTANTS
from apps.dashboards.permissions import GROUP_COORDINATION_ALT
from apps.dashboards.permissions import GROUP_COORDINATION
from apps.dashboards.permissions import GROUP_SUPERVISORS
from apps.dashboards.permissions import can_export_reports
from apps.dashboards.permissions import can_manage_dashboard
from apps.dashboards.permissions import can_view_sensitive_analytics
from apps.dashboards.permissions import has_dashboard_access
from apps.dashboards.permissions import is_assistant


def test_has_dashboard_access_requires_valid_group(django_user_model):
    user = django_user_model.objects.create_user(username='viewer', password='testpass123')

    assert has_dashboard_access(user) is False


def test_has_dashboard_access_allowed_for_assistant(django_user_model):
    user = django_user_model.objects.create_user(username='assistant-dashboard', password='testpass123')
    group, _ = Group.objects.get_or_create(name=GROUP_ASSISTANTS)
    user.groups.add(group)

    assert has_dashboard_access(user) is True


def test_sensitive_access_allowed_for_supervisor(django_user_model):
    user = django_user_model.objects.create_user(username='supervisor-perm', password='testpass123')
    group, _ = Group.objects.get_or_create(name=GROUP_SUPERVISORS)
    user.groups.add(group)

    assert can_view_sensitive_analytics(user) is True
    assert can_export_reports(user) is True


def test_sensitive_access_denied_for_assistant(django_user_model):
    user = django_user_model.objects.create_user(username='assistant-perm', password='testpass123')
    group, _ = Group.objects.get_or_create(name=GROUP_ASSISTANTS)
    user.groups.add(group)

    assert can_view_sensitive_analytics(user) is False
    assert can_export_reports(user) is False


def test_sensitive_access_allowed_for_coordination(django_user_model):
    user = django_user_model.objects.create_user(username='coord-perm', password='testpass123')
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATION)
    user.groups.add(group)

    assert can_view_sensitive_analytics(user) is True
    assert can_manage_dashboard(user) is True


def test_sensitive_access_allowed_for_coordination_with_accented_group(django_user_model):
    user = django_user_model.objects.create_user(username='coord-accent', password='testpass123')
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATION_ALT)
    user.groups.add(group)

    assert has_dashboard_access(user) is True
    assert can_view_sensitive_analytics(user) is True
    assert can_manage_dashboard(user) is True


def test_superuser_is_not_treated_as_assistant(django_user_model):
    user = django_user_model.objects.create_superuser(
        username='root',
        email='root@example.com',
        password='testpass123',
    )

    assert is_assistant(user) is False
    assert has_dashboard_access(user) is True


def test_manage_dashboard_denied_for_supervisor(django_user_model):
    user = django_user_model.objects.create_user(username='supervisor-manage', password='testpass123')
    group, _ = Group.objects.get_or_create(name=GROUP_SUPERVISORS)
    user.groups.add(group)

    assert can_manage_dashboard(user) is False


def test_setup_dashboard_groups_command_is_idempotent(db):
    call_command('setup_dashboard_groups')
    call_command('setup_dashboard_groups')

    assert Group.objects.filter(name=GROUP_ASSISTANTS).count() == 1
    assert Group.objects.filter(name=GROUP_SUPERVISORS).count() == 1
    assert Group.objects.filter(name=GROUP_COORDINATION).count() == 1


def test_seed_dashboard_groups_command_still_supported(db):
    call_command('seed_dashboard_groups')

    assert Group.objects.filter(name=GROUP_ASSISTANTS).count() == 1
    assert Group.objects.filter(name=GROUP_SUPERVISORS).count() == 1
    assert Group.objects.filter(name=GROUP_COORDINATION).count() == 1