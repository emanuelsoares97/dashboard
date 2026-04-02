from django.urls import path

from apps.imports_app.views import import_batch_detail, import_history, upload_excel

app_name = 'imports_app'

urlpatterns = [
    path('', upload_excel, name='upload_excel'),
    path('history/', import_history, name='history'),
    path('history/<int:batch_id>/', import_batch_detail, name='batch_detail'),
]
