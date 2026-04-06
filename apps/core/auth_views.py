from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse

from apps.dashboards.permissions import get_linked_agent
from apps.dashboards.permissions import is_assistant


class DashboardLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['username'].widget.attrs.update(
            {
                'class': 'login-input',
                'autocomplete': 'username',
                'autofocus': 'autofocus',
            }
        )
        form.fields['password'].widget.attrs.update(
            {
                'class': 'login-input',
                'autocomplete': 'current-password',
            }
        )
        return form

    def get_success_url(self):
        user = self.request.user
        if is_assistant(user):
            linked_agent = get_linked_agent(user)
            if linked_agent:
                return reverse('dashboards:assistant_detail', args=[linked_agent.id])
            return reverse('core:home')
        return super().get_success_url()


class DashboardLogoutView(LogoutView):
    next_page = 'core:login'