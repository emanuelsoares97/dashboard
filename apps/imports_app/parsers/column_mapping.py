"""Mapeamento explicito entre colunas reais do Excel e campos internos da V1."""

EXCEL_TO_INTERNAL_MAP = {
    'id_client': 'external_call_id',
    'name': 'agent_name',
    'startDate': 'start_date',
    'enddate': 'end_date',
    'service_type': 'service_type',
    'third_category': 'churn_reason',
    'resolution': 'retention_action',
    'Ret Resolution': 'final_outcome',
    'Day': 'day',
    'Week': 'week',
    'Month': 'month',
    'Exclude': 'exclude',
    'category': 'category',
    'subcategory': 'subcategory',
    'observations': 'observations',
}

# Estas colunas existem no ficheiro, mas nao entram na logica principal.
IGNORED_V1_COLUMNS = {
    'category2',
    'subcategory2',
    'subcategory2',
    'resolution2',
    'promote',
    'Tipe of service promoted',
    'actions',
    'Clients Status',
    'breakdown',
    'bonification',
    'id_apel',
    'User language',
    'Full Category',
    'Ret Group',
    'Customer Count',
    'Final Status',
    'msidn',
    'ticket',
}


def normalize_columns(columns: list[str]) -> dict[str, str]:
    """Renomeia apenas colunas exactas (case-sensitive) previstas para a V1."""
    renamed: dict[str, str] = {}
    for original in columns:
        target = EXCEL_TO_INTERNAL_MAP.get(original)
        if target:
            renamed[original] = target
    return renamed
