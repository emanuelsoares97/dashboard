from django import template

from apps.dashboards.permissions import can_access_imports
from apps.dashboards.permissions import get_linked_agent
from apps.dashboards.permissions import is_assistant

register = template.Library()


@register.filter
def user_is_assistant(user):
    return is_assistant(user)


@register.filter
def user_can_access_imports(user):
    return can_access_imports(user)


@register.filter
def linked_agent_id(user):
    linked_agent = get_linked_agent(user)
    if not linked_agent:
        return ''
    return linked_agent.id
