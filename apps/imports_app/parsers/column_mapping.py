COLUMN_ALIASES = {
    'external_call_id': ['external_call_id', 'call_id', 'id_chamada'],
    'team_name': ['team_name', 'team', 'equipe'],
    'agent_name': ['agent_name', 'agent', 'atendente'],
    'start_date': ['startdate', 'start_date', 'inicio', 'data_inicio'],
    'end_date': ['enddate', 'end_date', 'fim', 'data_fim'],
    'ret_resolution': ['ret_resolution', 'ret resolution', 'ret_resolucao'],
    'resolution': ['resolution', 'resolucao'],
    'third_category': ['third_category', '3rd_category', 'motivo_churn'],
    'service_type': ['service_type', 'tipo_servico'],
    'call_drop': ['call_drop', 'queda_ligacao'],
}


def normalize_columns(columns: list[str]) -> dict[str, str]:
    renamed = {}
    normalized = {column: column.strip().lower().replace(' ', '_') for column in columns}

    for original, normalized_name in normalized.items():
        for target, aliases in COLUMN_ALIASES.items():
            if normalized_name in aliases:
                renamed[original] = target
                break

    return renamed
