from apps.imports_app.parsers.column_mapping import normalize_columns


def test_normalize_columns_maps_only_exact_case_sensitive_names():
    columns = ['name', 'startDate', 'enddate', 'Ret Resolution', 'resolution', 'endDate', 'unknown']

    mapped = normalize_columns(columns)

    assert mapped['name'] == 'agent_name'
    assert mapped['startDate'] == 'start_date'
    assert mapped['enddate'] == 'end_date'
    assert mapped['Ret Resolution'] == 'final_outcome'
    assert mapped['resolution'] == 'retention_action'
    assert 'endDate' not in mapped
    assert 'unknown' not in mapped


def test_normalize_columns_ignores_irrelevant_columns():
    columns = ['ticket', 'resolution2', 'actions']

    mapped = normalize_columns(columns)

    assert mapped == {}
