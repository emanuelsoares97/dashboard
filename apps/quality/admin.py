from django.contrib import admin

from apps.quality.models import DataQualityFlag


@admin.register(DataQualityFlag)
class DataQualityFlagAdmin(admin.ModelAdmin):
	list_display = ('id', 'interaction', 'flag_type', 'severity', 'rule_code', 'detected_at', 'resolved_at')
	search_fields = ('rule_code', 'description', 'interaction__call_id_external', 'interaction__agent__name')
	list_filter = ('flag_type', 'severity', 'detected_at', 'resolved_at')
	date_hierarchy = 'detected_at'
