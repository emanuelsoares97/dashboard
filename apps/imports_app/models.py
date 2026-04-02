from django.conf import settings
from django.db import models
from django.utils import timezone


class ImportBatch(models.Model):
	class SourceType(models.TextChoices):
		MANUAL_EXCEL = 'manual_excel', 'Manual Excel'
		CSV = 'csv', 'CSV'
		API = 'api', 'API'

	class Status(models.TextChoices):
		PENDING = 'pending', 'Pending'
		PROCESSING = 'processing', 'Processing'
		SUCCESS = 'success', 'Success'
		PARTIAL = 'partial', 'Partial'
		FAILED = 'failed', 'Failed'

	source_type = models.CharField(max_length=30, choices=SourceType.choices, default=SourceType.MANUAL_EXCEL)
	original_filename = models.CharField(max_length=255, default='')
	stored_filename = models.CharField(max_length=255, blank=True)
	uploaded_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='import_batches',
	)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	source_schema_version = models.CharField(max_length=50, blank=True)
	total_rows = models.PositiveIntegerField(default=0)
	success_rows = models.PositiveIntegerField(default=0)
	failed_rows = models.PositiveIntegerField(default=0)
	flagged_rows = models.PositiveIntegerField(default=0)
	notes = models.TextField(blank=True)
	error_log = models.TextField(blank=True)
	imported_at = models.DateTimeField(default=timezone.now, editable=False)

	class Meta:
		ordering = ['-imported_at']

	def __str__(self):
		return f'{self.original_filename} ({self.status})'


class ImportRowRaw(models.Model):
	batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='raw_rows')
	source_row_number = models.PositiveIntegerField()
	raw_payload = models.JSONField()
	raw_hash = models.CharField(max_length=64, blank=True)
	processed_interaction = models.OneToOneField(
		'inbound.Interaction',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='source_row',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['batch_id', 'source_row_number']
		constraints = [
			models.UniqueConstraint(
				fields=['batch', 'source_row_number'],
				name='unique_raw_row_per_batch',
			),
		]

	def __str__(self):
		return f'Batch {self.batch_id} row {self.source_row_number}'
