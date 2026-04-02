from datetime import timedelta

from django.db import models


class CallRecord(models.Model):
	"""One report row equals one call record."""

	external_call_id = models.CharField(max_length=100, blank=True)
	team_name = models.CharField(max_length=120)
	agent_name = models.CharField(max_length=120)
	start_date = models.DateTimeField(db_index=True)
	end_date = models.DateTimeField(db_index=True)
	ret_resolution = models.CharField(max_length=120, db_index=True)
	resolution = models.CharField(max_length=120, db_index=True)
	third_category = models.CharField(max_length=120, blank=True, db_index=True)
	service_type = models.CharField(max_length=120, blank=True, db_index=True)
	call_drop = models.BooleanField(default=False)
	duration_seconds = models.PositiveIntegerField(default=0)
	source_file_row = models.PositiveIntegerField(null=True, blank=True)
	batch = models.ForeignKey(
		'imports_app.ImportBatch',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='call_records',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-start_date']

	def save(self, *args, **kwargs):
		if self.start_date and self.end_date:
			delta: timedelta = self.end_date - self.start_date
			self.duration_seconds = max(int(delta.total_seconds()), 0)
		super().save(*args, **kwargs)

	@property
	def final_outcome(self) -> str:
		if self.call_drop:
			return 'Call Drop'
		return self.ret_resolution

	def __str__(self):
		return f'{self.agent_name} | {self.ret_resolution} | {self.start_date:%Y-%m-%d %H:%M}'
