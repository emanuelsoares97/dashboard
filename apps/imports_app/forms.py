from django import forms


class ExcelUploadForm(forms.Form):
    file = forms.FileField(
        label='Arquivo Excel',
        help_text='Envie um arquivo .xlsx com os dados de inbound.',
    )
