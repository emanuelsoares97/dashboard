from django.db import models


class ImportBatch(models.Model):
	class Status(models.TextChoices):
		PENDING = 'pending', 'Pending'
		PROCESSING = 'processing', 'Processing'
		DONE = 'done', 'Done'
		FAILED = 'failed', 'Failed'

	uploaded_filename = models.CharField(max_length=255)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	total_rows = models.PositiveIntegerField(default=0)
	imported_rows = models.PositiveIntegerField(default=0)
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.uploaded_filename} ({self.status})'
