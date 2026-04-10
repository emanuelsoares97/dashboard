from pathlib import Path
import threading

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from django.shortcuts import redirect, render
from django.db import close_old_connections

from apps.dashboards.permissions import require_imports_access
from apps.imports_app.forms import ExcelUploadForm
from apps.imports_app.models import ImportBatch


def _store_uploaded_file(excel_file):
    """Guarda o ficheiro localmente para manter rastreabilidade do lote importado."""
    destination_dir = Path(settings.MEDIA_ROOT) / 'imports'
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / excel_file.name

    with destination_path.open('wb+') as target:
        for chunk in excel_file.chunks():
            target.write(chunk)

    return destination_path


def _create_import_batch(*, excel_file, request):
    return ImportBatch.objects.create(
        original_filename=excel_file.name,
        stored_filename=excel_file.name,
        source_type=ImportBatch.SourceType.MANUAL_EXCEL,
        uploaded_by=request.user if request.user.is_authenticated else None,
    )


def _run_import_job(*, batch_id, destination_path, import_excel_func):
    close_old_connections()
    try:
        batch = ImportBatch.objects.get(id=batch_id)
        import_excel_func(destination_path, batch)
    except Exception as exc:  # pragma: no cover - defensive background guard
        ImportBatch.objects.filter(id=batch_id).update(
            status=ImportBatch.Status.FAILED,
            error_log=str(exc),
        )
    finally:
        close_old_connections()


def _is_ajax_request(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _parse_progress_note(notes):
    if not notes or not notes.startswith('PROGRESS|'):
        return {}

    parsed = {}
    for chunk in notes.split('|')[1:]:
        if '=' not in chunk:
            continue
        key, raw_value = chunk.split('=', 1)
        try:
            parsed[key] = int(raw_value)
        except ValueError:
            continue
    return parsed


def _build_status_payload(batch):
    progress_note = _parse_progress_note(batch.notes)
    total_rows = batch.total_rows or progress_note.get('total', 0)
    processed_rows = progress_note.get(
        'processed',
        batch.success_rows + batch.duplicate_rows + batch.failed_rows,
    )
    processed_rows = max(processed_rows, 0)
    total_rows = max(total_rows, 0)

    progress_pct = 0
    if total_rows > 0:
        progress_pct = min(100, round((processed_rows / total_rows) * 100))

    if batch.status in {ImportBatch.Status.SUCCESS, ImportBatch.Status.PARTIAL, ImportBatch.Status.FAILED}:
        progress_pct = 100

    elapsed_seconds = max(0, int((timezone.now() - batch.imported_at).total_seconds()))
    eta_seconds = None
    if batch.status == ImportBatch.Status.PROCESSING and processed_rows > 0 and total_rows > processed_rows:
        remaining_rows = total_rows - processed_rows
        eta_seconds = int((elapsed_seconds / processed_rows) * remaining_rows)

    return {
        'batch_id': batch.id,
        'status': batch.status,
        'progress_pct': progress_pct,
        'processed_rows': processed_rows,
        'total_rows': total_rows,
        'elapsed_seconds': elapsed_seconds,
        'eta_seconds': eta_seconds,
        'success_rows': batch.success_rows,
        'duplicate_rows': batch.duplicate_rows,
        'failed_rows': batch.failed_rows,
        'error_log': batch.error_log,
        'notes': batch.notes,
    }


@require_imports_access
def import_status(request, batch_id):
    try:
        batch = ImportBatch.objects.get(id=batch_id)
    except ImportBatch.DoesNotExist:
        return JsonResponse({'detail': 'Lote nao encontrado.'}, status=404)

    return JsonResponse(_build_status_payload(batch))


@require_imports_access
def handle_upload_excel(request, *, import_excel_func):
    """Recebe um ficheiro manual, cria o lote e desencadeia a importacao."""
    form = ExcelUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        excel_file = form.cleaned_data['file']
        destination_path = _store_uploaded_file(excel_file)

        batch = _create_import_batch(excel_file=excel_file, request=request)
        batch.stored_filename = destination_path.name
        batch.save(update_fields=['stored_filename'])

        if _is_ajax_request(request):
            thread = threading.Thread(
                target=_run_import_job,
                kwargs={
                    'batch_id': batch.id,
                    'destination_path': destination_path,
                    'import_excel_func': import_excel_func,
                },
                daemon=True,
            )
            thread.start()
            return JsonResponse(
                {
                    'batch_id': batch.id,
                    'status_url': reverse('imports_app:import_status', args=[batch.id]),
                },
                status=202,
            )

        try:
            summary = import_excel_func(destination_path, batch)
            messages.success(
                request,
                (
                    'Importacao concluida com sucesso. '
                    f"Linhas: {summary['imported_rows']} | "
                    f"Duplicadas ignoradas: {summary['duplicate_rows']} | "
                    f"Dup. no ficheiro: {summary['duplicate_in_file_rows']} | "
                    f"Dup. anteriores: {summary['duplicate_previous_rows']} | "
                    f"Inconsistencias: {summary['inconsistencies']}"
                ),
            )
        except Exception as exc:
            batch.status = ImportBatch.Status.FAILED
            batch.error_log = str(exc)
            batch.save(update_fields=['status', 'error_log'])
            messages.error(request, f'Falha na importacao: {exc}')

        return redirect('imports_app:upload_excel')

    context = {
        'form': form,
        'recent_batches': ImportBatch.objects.all()[:10],
    }
    return render(request, 'imports_app/upload.html', context)