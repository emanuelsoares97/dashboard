from apps.imports_app.services import import_excel

from .pages import import_batch_detail
from .pages import import_history
from .upload import import_status
from .upload import handle_upload_excel


def upload_excel(request):
    return handle_upload_excel(request, import_excel_func=import_excel)