from django.db.models import Prefetch

from apps.imports_app.models import ImportBatch, ImportRowRaw
from apps.quality.models import DataQualityFlag


def list_import_batches(*, page_number=1, per_page=20):
    """Devolve lotes paginados para historico operacional de importacoes."""
    from django.core.paginator import Paginator

    queryset = ImportBatch.objects.all().order_by('-imported_at', '-id')
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(page_number)


def get_import_batch_detail(batch_id: int) -> ImportBatch:
    """Carrega detalhe operacional de um lote com dados necessarios para auditoria."""
    queryset = (
        ImportBatch.objects.select_related('uploaded_by')
        .prefetch_related(
            Prefetch(
                'raw_rows',
                queryset=ImportRowRaw.objects.order_by('source_row_number'),
            )
        )
    )
    return queryset.get(id=batch_id)


def build_batch_detail_context(batch: ImportBatch, *, sample_size=10) -> dict:
    """Monta contexto de detalhe de lote sem colocar logica na view."""
    inconsistency_qs = DataQualityFlag.objects.filter(
        interaction__batch=batch,
        flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
    ).select_related('interaction__agent')

    raw_rows = batch.raw_rows.all()
    return {
        'batch': batch,
        'samples': {
            'duplicate_in_file': raw_rows.filter(
                processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_IN_FILE
            )[:sample_size],
            'duplicate_previous': raw_rows.filter(
                processing_status=ImportRowRaw.ProcessingStatus.DUPLICATE_PREVIOUS
            )[:sample_size],
            'failed_rows': raw_rows.filter(
                processing_status=ImportRowRaw.ProcessingStatus.FAILED_VALIDATION
            )[:sample_size],
        },
        'inconsistency_total': inconsistency_qs.count(),
        'inconsistency_samples': inconsistency_qs[:sample_size],
    }