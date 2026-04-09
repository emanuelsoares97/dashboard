import csv
from pathlib import Path

import pandas as pd

from apps.imports_app.parsers.column_mapping import normalize_columns


def _read_csv_dataframe(file_path: Path) -> pd.DataFrame:
    for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            return pd.read_csv(
                file_path,
                sep='|',
                dtype=str,
                keep_default_na=False,
                engine='python',
                quoting=csv.QUOTE_NONE,
                encoding=encoding,
            )
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError('csv', b'', 0, 1, 'Nao foi possivel decodificar o CSV.')


def read_excel_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == '.csv':
        dataframe = _read_csv_dataframe(file_path)
    else:
        dataframe = pd.read_excel(file_path)
    return dataframe.rename(columns=normalize_columns(dataframe.columns.tolist()))


def iter_row_payloads(dataframe: pd.DataFrame):
    for row_number, row in enumerate(dataframe.to_dict(orient='records'), start=2):
        yield row_number, row
