from collections.abc import Iterable

REQUIRED_COLUMNS = [
    'agent_name',
    'start_date',
    'end_date',
    'final_outcome',
]

HINTS_BY_INTERNAL_COLUMN = {
    'agent_name': "Esperado: 'name'",
    'start_date': "Esperado: 'startDate'",
    'end_date': "Esperado: 'enddate' (nao 'endDate')",
    'final_outcome': "Esperado: 'Ret Resolution' (com espaco)",
}


def validate_required_columns(columns: Iterable[str]) -> None:
    available = set(columns)
    missing = [column for column in REQUIRED_COLUMNS if column not in available]
    if missing:
        hints = [HINTS_BY_INTERNAL_COLUMN.get(column, column) for column in missing]
        raise ValueError(
            'Colunas obrigatorias ausentes no Excel mapeado: '
            f"{', '.join(missing)}. Dica: {' | '.join(hints)}"
        )
