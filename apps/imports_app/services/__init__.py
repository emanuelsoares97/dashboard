from pathlib import Path

from apps.imports_app.parsers.excel_reader import iter_row_payloads, read_excel_dataframe
from apps.imports_app.parsers.row_mapper import build_raw_hash, is_retention_category, map_row
from apps.imports_app.persistence.import_writer import create_raw_row, persist_interaction
from apps.imports_app.rules.inconsistencies import detect_inconsistencies
from apps.imports_app.validators.file_validator import validate_required_columns
from apps.imports_app.validators.row_validator import validate_row

from .batches import build_batch_detail_context
from .batches import get_import_batch_detail
from .batches import list_import_batches
from .pipeline import run_import_excel


def import_excel(file_path: Path, batch) -> dict:
    return run_import_excel(
        file_path,
        batch,
        read_excel_dataframe=read_excel_dataframe,
        validate_required_columns=validate_required_columns,
        iter_row_payloads=iter_row_payloads,
        map_row=map_row,
        build_raw_hash=build_raw_hash,
        create_raw_row=create_raw_row,
        validate_row=validate_row,
        detect_inconsistencies=detect_inconsistencies,
        persist_interaction=persist_interaction,
        is_retention_category=is_retention_category,
    )