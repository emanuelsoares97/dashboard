from django.db import models


class TipificationInconsistency(models.Model):
	"""Tracks rows where resolution is pending but final retention says retained."""

	call = models.OneToOneField(
		'inbound.CallRecord', on_delete=models.CASCADE, related_name='tipification_inconsistency'
	)
	reason = models.CharField(max_length=255)
	detected_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-detected_at']

	def __str__(self):
		return f'Inconsistency call={self.call_id}'
