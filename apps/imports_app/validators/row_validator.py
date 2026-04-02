from apps.imports_app.types import ImportRowData, RowValidationResult


def validate_row(row_data: ImportRowData) -> RowValidationResult:
    errors: list[str] = []

    if not row_data.agent_name:
        errors.append('name is required')
    if not row_data.final_outcome:
        errors.append('Ret Resolution is required')
    if row_data.start_at is None:
        errors.append('startDate is invalid or missing')
    if row_data.end_at is None:
        errors.append('enddate is invalid or missing')
    if row_data.start_at and row_data.end_at and row_data.end_at < row_data.start_at:
        errors.append('enddate must be after startDate')

    return RowValidationResult(row_data=row_data, errors=errors)
