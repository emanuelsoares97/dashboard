from django.urls import path

from apps.imports_app.views import upload_excel

app_name = 'imports_app'

urlpatterns = [
    path('', upload_excel, name='upload_excel'),
]
