from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from apps.imports_app.forms import ExcelUploadForm
from apps.imports_app.models import ImportBatch
from apps.imports_app.services import import_excel


def upload_excel(request):
	form = ExcelUploadForm(request.POST or None, request.FILES or None)

	if request.method == 'POST' and form.is_valid():
		excel_file = form.cleaned_data['file']
		destination_dir = Path(settings.MEDIA_ROOT) / 'imports'
		destination_dir.mkdir(parents=True, exist_ok=True)
		destination_path = destination_dir / excel_file.name

		with destination_path.open('wb+') as target:
			for chunk in excel_file.chunks():
				target.write(chunk)

		batch = ImportBatch.objects.create(uploaded_filename=excel_file.name)

		try:
			summary = import_excel(destination_path, batch)
			messages.success(
				request,
				(
					'Importacao concluida com sucesso. '
					f"Linhas: {summary['imported_rows']} | "
					f"Inconsistencias: {summary['inconsistencies']}"
				),
			)
		except Exception as exc:
			batch.status = ImportBatch.Status.FAILED
			batch.notes = str(exc)
			batch.save(update_fields=['status', 'notes'])
			messages.error(request, f'Falha na importacao: {exc}')

		return redirect('imports_app:upload_excel')

	context = {
		'form': form,
		'recent_batches': ImportBatch.objects.all()[:10],
	}
	return render(request, 'imports_app/upload.html', context)
