from django.contrib import admin

from apps.inbound.models import Agent, ChurnReason, Interaction, OutcomeFinal, RetentionAction, ServiceType, Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
	list_display = ('name', 'external_code', 'is_active', 'created_at')
	search_fields = ('name', 'external_code')
	list_filter = ('is_active',)


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
	list_display = ('name', 'team', 'external_code', 'is_active', 'created_at')
	search_fields = ('name', 'external_code', 'team__name')
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
