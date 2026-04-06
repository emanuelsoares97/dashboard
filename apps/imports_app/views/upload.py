from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

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


def handle_upload_excel(request, *, import_excel_func):
    """Recebe um ficheiro Excel manual, cria o lote e desencadeia a importacao."""
    form = ExcelUploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        excel_file = form.cleaned_data['file']
        destination_path = _store_uploaded_file(excel_file)

        batch = _create_import_batch(excel_file=excel_file, request=request)
        batch.stored_filename = destination_path.name
        batch.save(update_fields=['stored_filename'])

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