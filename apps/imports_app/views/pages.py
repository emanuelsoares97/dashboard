from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render

from apps.dashboards.permissions import require_imports_access
from apps.imports_app.services import build_batch_detail_context
from apps.imports_app.services import get_import_batch_detail
from apps.imports_app.services import list_import_batches


@require_imports_access
def import_history(request):
    """Lista o historico paginado dos lotes para rastreabilidade operacional."""
    page_number = request.GET.get('page', '1')
    batches_page = list_import_batches(page_number=page_number, per_page=20)

    context = {
        'batches_page': batches_page,
    }
    return render(request, 'imports_app/history.html', context)


@require_imports_access
def import_batch_detail(request, batch_id):
    """Mostra detalhe operativo de um lote especifico com amostras de auditoria."""
    try:
        batch = get_import_batch_detail(batch_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Lote de importacao nao encontrado.')
        return redirect('imports_app:history')

    context = build_batch_detail_context(batch)
    return render(request, 'imports_app/batch_detail.html', context)