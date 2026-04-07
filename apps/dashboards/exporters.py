import csv
from datetime import date

from django.http import HttpResponse


def _format_decimal(value):
    """Formata valores numericos para duas casas decimais no CSV."""
    if value is None:
        return ''
    return f'{float(value):.2f}'


def _build_filename(prefix, filters, *, default_suffix='geral'):
    """Constroi nome de ficheiro consistente a partir do intervalo ativo."""
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')

    if isinstance(start_date, date) and isinstance(end_date, date):
        suffix = f'{start_date:%Y%m%d}_{end_date:%Y%m%d}'
    else:
        suffix = default_suffix

    return f'{prefix}_{suffix}.csv'


def _build_csv_response(*, filename, headers, rows):
    """Devolve resposta HTTP com conteudo CSV pronto para download."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

    return response


def export_assistants_csv(rows, filters):
    """Exporta ranking de assistentes para CSV."""
    filename = _build_filename('assistentes', filters)
    headers = [
        'Assistente',
        'Total chamadas',
        'Duracao media (s)',
        'Total retidos',
        'Total nao retidos',
        'Taxa retencao (%)',
        'Taxa nao retencao (%)',
        'Taxa call drop (%)',
        'Taxa inconsistencias (%)',
    ]
    csv_rows = [
        [
            row['assistant_name'],
            row['total_calls'],
            _format_decimal(row['avg_duration_seconds']),
            row['total_retained'],
            row['total_non_retained'],
            _format_decimal(row['retention_rate']),
            _format_decimal(row['non_retention_rate']),
            _format_decimal(row['call_drop_rate']),
            _format_decimal(row['inconsistency_rate']),
        ]
        for row in rows
    ]
    return _build_csv_response(filename=filename, headers=headers, rows=csv_rows)


def export_monthly_rates_csv(rows, filters):
    """Exporta tabela de taxas mensais para CSV."""
    filename = _build_filename('taxas_mensais', filters, default_suffix='historico')
    headers = [
        'Mes',
        'Total chamadas',
        'Total retidos',
        'Total nao retidos',
        'Total call drop',
        'Taxa retencao (%)',
        'Taxa nao retencao (%)',
        'Taxa call drop (%)',
    ]
    csv_rows = [
        [
            row['month'],
            row['total_calls'],
            row['total_retained'],
            row['total_non_retained'],
            row['total_call_drop'],
            _format_decimal(row['retention_rate']),
            _format_decimal(row['non_retention_rate']),
            _format_decimal(row['call_drop_rate']),
        ]
        for row in rows
    ]
    return _build_csv_response(filename=filename, headers=headers, rows=csv_rows)


def export_daily_rates_csv(rows, filters):
    """Exporta tabela de taxas diarias para CSV."""
    filename = _build_filename('taxas_diarias', filters)
    headers = [
        'Dia',
        'Total chamadas',
        'Total retidos',
        'Total nao retidos',
        'Total call drop',
        'Taxa retencao (%)',
        'Taxa nao retencao (%)',
        'Taxa call drop (%)',
    ]
    csv_rows = [
        [
            row['day'],
            row['total_calls'],
            row['total_retained'],
            row['total_non_retained'],
            row['total_call_drop'],
            _format_decimal(row['retention_rate']),
            _format_decimal(row['non_retention_rate']),
            _format_decimal(row['call_drop_rate']),
        ]
        for row in rows
    ]
    return _build_csv_response(filename=filename, headers=headers, rows=csv_rows)


def export_services_csv(rows, filters):
    """Exporta tabela de servicos para CSV."""
    filename = _build_filename('servicos', filters)
    headers = [
        'Servico',
        'Total chamadas',
        'Taxa retencao (%)',
        'Taxa nao retencao (%)',
        'Taxa call drop (%)',
    ]
    csv_rows = [
        [
            row['service_type'],
            row['total_calls'],
            _format_decimal(row['retention_rate']),
            _format_decimal(row['non_retention_rate']),
            _format_decimal(row['call_drop_rate']),
        ]
        for row in rows
    ]
    return _build_csv_response(filename=filename, headers=headers, rows=csv_rows)


def export_inconsistencies_csv(section, filters):
    """Exporta detalhe de inconsistencias para CSV."""
    filename = _build_filename('inconsistencias', filters)
    headers = [
        'Assistente',
        'Motivo',
        'Acao',
        'Resultado final',
        'Tipo de inconsistencia',
    ]
    csv_rows = [
        [
            row['assistant_name'],
            row['churn_reason'],
            row['retention_action'],
            row['final_outcome'],
            row['inconsistency_type'],
        ]
        for row in section['table']
    ]
    return _build_csv_response(filename=filename, headers=headers, rows=csv_rows)


def export_typing_analysis_csv(rows, filters, *, day_filter=None):
    """Exporta análise de tipificações para CSV (geral ou filtrado por dia)."""
    if day_filter:
        filename = _build_filename('tipificacoes', {'start_date': day_filter, 'end_date': day_filter})
    else:
        filename = _build_filename('tipificacoes', filters)

    headers = [
        'Assistente',
        'Data',
        'Categoria',
        'Subcategoria',
        'Motivo de corte',
        'Observacao',
        'Status',
        'Score utilizado',
        'Melhor score',
        'Delta',
        'Melhor sugestao',
        'Razao',
    ]
    csv_rows = [
        [
            row['assistant_name'],
            row['occurred_on'],
            row['category'],
            row['subcategory'],
            row['third_category'],
            row['observations'],
            row['status_label'],
            _format_decimal(row['used_score']),
            _format_decimal(row['best_score']),
            _format_decimal(row['delta']),
            row['suggestion'] or '',
            row['reason'],
        ]
        for row in rows
    ]
    return _build_csv_response(filename=filename, headers=headers, rows=csv_rows)