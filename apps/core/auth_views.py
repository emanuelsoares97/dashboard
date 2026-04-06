from django.contrib.auth.views import LoginView, LogoutView


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


class DashboardLogoutView(LogoutView):
    next_page = 'core:login'