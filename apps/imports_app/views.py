from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render

from apps.imports_app.forms import ExcelUploadForm
from apps.imports_app.models import ImportBatch
from apps.imports_app.services import (
	build_batch_detail_context,
	get_import_batch_detail,
	import_excel,
	list_import_batches,
)


def upload_excel(request):
	"""Recebe um ficheiro Excel manual, cria o lote e desencadeia a importacao."""
	form = ExcelUploadForm(request.POST or None, request.FILES or None)

	if request.method == 'POST' and form.is_valid():
		excel_file = form.cleaned_data['file']
		# O ficheiro fica guardado localmente para manter rastreabilidade do lote importado.
		destination_dir = Path(settings.MEDIA_ROOT) / 'imports'
		destination_dir.mkdir(parents=True, exist_ok=True)
		destination_path = destination_dir / excel_file.name

		with destination_path.open('wb+') as target:
			for chunk in excel_file.chunks():
				target.write(chunk)

		batch = ImportBatch.objects.create(
			original_filename=excel_file.name,
			stored_filename=destination_path.name,
			source_type=ImportBatch.SourceType.MANUAL_EXCEL,
			uploaded_by=request.user if request.user.is_authenticated else None,
		)

		try:
			# A logica de ingestao fica fora da view para nao misturar UI com processamento.
			summary = import_excel(destination_path, batch)
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


def import_history(request):
	"""Lista o historico paginado dos lotes para rastreabilidade operacional."""
	page_number = request.GET.get('page', '1')
	batches_page = list_import_batches(page_number=page_number, per_page=20)

	context = {
		'batches_page': batches_page,
	}
	return render(request, 'imports_app/history.html', context)


def import_batch_detail(request, batch_id):
	"""Mostra detalhe operativo de um lote especifico com amostras de auditoria."""
	try:
		batch = get_import_batch_detail(batch_id)
	except ObjectDoesNotExist:
		messages.error(request, 'Lote de importacao nao encontrado.')
		return redirect('imports_app:history')

	context = build_batch_detail_context(batch)
	return render(request, 'imports_app/batch_detail.html', context)
