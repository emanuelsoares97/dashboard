from django import forms


class ExcelUploadForm(forms.Form):
    file = forms.FileField(
        label='Arquivo CSV ou Excel',
        help_text='Envie o ficheiro recebido (.csv ou .xlsx) com os dados de inbound.',
    )
