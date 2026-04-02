from collections.abc import Iterable

REQUIRED_COLUMNS = [
    'team_name',
    'agent_name',
    'start_date',
    'end_date',
    'ret_resolution',
    'resolution',
]


def validate_required_columns(columns: Iterable[str]) -> None:
    available = set(columns)
    missing = [column for column in REQUIRED_COLUMNS if column not in available]
    if missing:
        raise ValueError(f'Colunas obrigatorias ausentes: {", ".join(missing)}')
