from django import forms
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.inbound.models import Agent, ChurnReason, Interaction, OutcomeFinal, RetentionAction, ServiceType, Team


User = get_user_model()


class UserAgentLinkForm(forms.ModelForm):
	agent = forms.ModelChoiceField(
		queryset=Agent.objects.none(),
		required=False,
		label='Assistente associado',
		help_text='Selecione o assistente da base analítica ligado a este utilizador.',
	)

	class Meta:
		model = User
		fields = '__all__'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		instance = self.instance

		if not instance or not instance.pk:
			self.fields['agent'].queryset = Agent.objects.none()
			return

		self.fields['agent'].queryset = Agent.objects.filter(user__isnull=True) | Agent.objects.filter(
			user=instance
		)

		linked_agent = Agent.objects.filter(user=instance).first()
		if linked_agent:
			self.fields['agent'].initial = linked_agent

	def save(self, commit=True):
		user = super().save(commit=commit)
		selected_agent = self.cleaned_data.get('agent')

		# Garante 1:1: remove ligacoes antigas deste utilizador antes de aplicar a nova.
		Agent.objects.filter(user=user).update(user=None)

		if selected_agent:
			selected_agent.user = user
			selected_agent.save(update_fields=['user'])

		return user


class DashboardUserAdmin(BaseUserAdmin):
	form = UserAgentLinkForm
	list_display = BaseUserAdmin.list_display + ('linked_agent',)
	search_fields = BaseUserAdmin.search_fields + ('agent_profile__name', 'agent_profile__team__name')
	list_filter = BaseUserAdmin.list_filter + ('agent_profile__team',)
	fieldsets = BaseUserAdmin.fieldsets + (
		(
			'Ligação ao assistente',
			{
				'fields': ('agent',),
			},
		),
	)

	@admin.display(description='Assistente associado')
	def linked_agent(self, obj):
		agent = getattr(obj, 'agent_profile', None)
		if not agent:
			return '-'
		return str(agent)


try:
	admin.site.unregister(User)
except NotRegistered:
	pass

admin.site.register(User, DashboardUserAdmin)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
	list_display = ('name', 'external_code', 'is_active', 'created_at')
	search_fields = ('name', 'external_code')
	list_filter = ('is_active',)


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
	list_display = ('name', 'team', 'user', 'external_code', 'is_active', 'created_at')
	fields = ('name', 'team', 'user', 'external_code', 'is_active')
	autocomplete_fields = ('user',)
	list_select_related = ('team', 'user')
	search_fields = (
		'name',
		'external_code',
		'team__name',
		'user__username',
		'user__first_name',
		'user__last_name',
	)
	list_filter = ('is_active', 'team')


@admin.register(OutcomeFinal)
class OutcomeFinalAdmin(admin.ModelAdmin):
	list_display = ('label', 'code', 'is_call_drop_outcome')
	search_fields = ('label', 'code')
	list_filter = ('is_call_drop_outcome',)


@admin.register(RetentionAction)
class RetentionActionAdmin(admin.ModelAdmin):
	list_display = ('label', 'code', 'is_pending')
	search_fields = ('label', 'code')
	list_filter = ('is_pending',)


@admin.register(ChurnReason)
class ChurnReasonAdmin(admin.ModelAdmin):
	list_display = ('label', 'code', 'category_group')
	search_fields = ('label', 'code', 'category_group')


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
	list_display = ('label', 'code')
	search_fields = ('label', 'code')


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'call_id_external',
		'agent',
		'team',
		'final_outcome',
		'retention_action',
		'service_type',
		'occurred_on',
		'is_call_drop',
	)
	search_fields = (
		'call_id_external',
		'agent__name',
		'team__name',
		'final_outcome__label',
		'retention_action__label',
		'service_type__label',
	)
	list_filter = ('direction', 'is_call_drop', 'occurred_on', 'team', 'service_type', 'final_outcome')
	date_hierarchy = 'occurred_on'
