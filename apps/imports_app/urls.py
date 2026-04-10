from django.urls import path

from apps.imports_app.views import import_batch_detail, import_history, import_status, upload_excel

app_name = 'imports_app'

urlpatterns = [
    path('', upload_excel, name='upload_excel'),
    path('status/<int:batch_id>/', import_status, name='import_status'),
    path('history/', import_history, name='history'),
    path('history/<int:batch_id>/', import_batch_detail, name='batch_detail'),
]
