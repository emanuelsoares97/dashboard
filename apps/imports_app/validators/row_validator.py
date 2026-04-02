from apps.imports_app.types import ImportRowData, RowValidationResult


def validate_row(row_data: ImportRowData) -> RowValidationResult:
    errors: list[str] = []

    if not row_data.team_name:
        errors.append('team_name is required')
    if not row_data.agent_name:
        errors.append('agent_name is required')
    if not row_data.ret_resolution:
        errors.append('ret_resolution is required')
    if not row_data.resolution:
        errors.append('resolution is required')
    if row_data.start_at is None:
        errors.append('start_date is invalid or missing')
    if row_data.end_at is None:
        errors.append('end_date is invalid or missing')
    if row_data.start_at and row_data.end_at and row_data.end_at < row_data.start_at:
        errors.append('end_date must be after start_date')

    return RowValidationResult(row_data=row_data, errors=errors)
