from django.contrib import admin, messages
from django.db import transaction

from apps.imports_app.models import ImportBatch, ImportRowRaw
from apps.inbound.models import Interaction


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
	list_display = (
		'id',
		'original_filename',
		'status',
		'source_type',
		'total_rows',
		'success_rows',
		'failed_rows',
		'imported_at',
	)
	search_fields = ('original_filename', 'stored_filename', 'notes', 'error_log')
	list_filter = ('status', 'source_type', 'imported_at')
	date_hierarchy = 'imported_at'
	actions = ('delete_batches_and_related',)

	@admin.action(description='Apagar batches selecionados e interacoes relacionadas')
	def delete_batches_and_related(self, request, queryset):
		"""Remove batches e dependencias protegidas de forma controlada."""
		batch_ids = list(queryset.values_list('id', flat=True))
		interactions_qs = Interaction.objects.filter(batch_id__in=batch_ids)
		total_batches = len(batch_ids)
		total_interactions = interactions_qs.count()

		with transaction.atomic():
			interactions_qs.delete()
			queryset.delete()

		self.message_user(
			request,
			f'Removidos {total_batches} batch(s) e {total_interactions} interacao(oes) relacionadas.',
			level=messages.SUCCESS,
		)


@admin.register(ImportRowRaw)
class ImportRowRawAdmin(admin.ModelAdmin):
	list_display = ('id', 'batch', 'source_row_number', 'processing_status', 'processed_interaction', 'created_at')
	search_fields = ('raw_hash', 'processing_error', 'batch__original_filename')
	list_filter = ('processing_status', 'created_at')
	date_hierarchy = 'created_at'
