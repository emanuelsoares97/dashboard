from django.conf import settings
from django.db import models


class DataQualityFlag(models.Model):
	class FlagType(models.TextChoices):
		TIPIFICATION_INCONSISTENCY = 'tipification_inconsistency', 'Tipification Inconsistency'
		DURATION_INVALID = 'duration_invalid', 'Duration Invalid'
		MISSING_REQUIRED = 'missing_required', 'Missing Required'

	class Severity(models.TextChoices):
		INFO = 'info', 'Info'
		WARNING = 'warning', 'Warning'
		ERROR = 'error', 'Error'

	interaction = models.ForeignKey(
		'inbound.Interaction', on_delete=models.CASCADE, related_name='quality_flags'
	)
	flag_type = models.CharField(max_length=50, choices=FlagType.choices)
	rule_code = models.CharField(max_length=100)
	severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
	description = models.CharField(max_length=255)
	detected_at = models.DateTimeField(auto_now_add=True)
	resolved_at = models.DateTimeField(null=True, blank=True)
	resolved_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='resolved_quality_flags',
	)
	resolution_notes = models.TextField(blank=True)

	class Meta:
		ordering = ['-detected_at']
		indexes = [
			models.Index(fields=['flag_type', 'severity']),
		]

	def __str__(self):
		return f'{self.flag_type} for interaction={self.interaction_id}'
