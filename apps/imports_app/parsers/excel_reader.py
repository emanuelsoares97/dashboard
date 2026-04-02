from pathlib import Path

import pandas as pd

from apps.imports_app.parsers.column_mapping import normalize_columns


def read_excel_dataframe(file_path: Path) -> pd.DataFrame:
    dataframe = pd.read_excel(file_path)
    return dataframe.rename(columns=normalize_columns(dataframe.columns.tolist()))


def iter_row_payloads(dataframe: pd.DataFrame):
    for row_number, row in enumerate(dataframe.to_dict(orient='records'), start=2):
        yield row_number, row
