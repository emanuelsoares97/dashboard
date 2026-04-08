from pathlib import Path
import os
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from apps.imports_app.parsers.excel_reader import read_excel_dataframe, iter_row_payloads  # noqa: E402
from apps.imports_app.parsers.row_mapper import map_row  # noqa: E402
from apps.imports_app.validators.file_validator import validate_required_columns  # noqa: E402
from apps.imports_app.validators.row_validator import validate_row  # noqa: E402


def main() -> None:
    file_path = PROJECT_ROOT / 'tip ret (2).xlsx'
    df = read_excel_dataframe(file_path)

    validate_required_columns(df.columns)

    invalid_rows = []
    final_outcome_counts = {}
    retention_action_counts = {}
    churn_reason_counts = {}

    total_rows = 0
    valid_rows = 0

    for row_number, row_payload in iter_row_payloads(df):
        total_rows += 1
        row_data = map_row(row_number, row_payload)
        result = validate_row(row_data)
        if not result.is_valid:
            invalid_rows.append(
                {
                    'row_number': row_number,
                    'errors': result.errors,
                }
            )
            continue

        valid_rows += 1

        fo = (result.row_data.final_outcome or '').strip() or '<empty>'
        ra = (result.row_data.retention_action or '').strip() or '<empty>'
        cr = (result.row_data.churn_reason or '').strip() or '<empty>'

        final_outcome_counts[fo] = final_outcome_counts.get(fo, 0) + 1
        retention_action_counts[ra] = retention_action_counts.get(ra, 0) + 1
        churn_reason_counts[cr] = churn_reason_counts.get(cr, 0) + 1

    report = {
        'file': str(file_path),
        'total_rows': total_rows,
        'valid_rows': valid_rows,
        'invalid_rows_count': len(invalid_rows),
        'invalid_rows_sample': invalid_rows[:20],
        'final_outcome_counts_top20': sorted(
            final_outcome_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20],
        'retention_action_counts_top20': sorted(
            retention_action_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20],
        'churn_reason_counts_top20': sorted(
            churn_reason_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20],
        'sem_acao_count': retention_action_counts.get('Sem acao', 0),
        'pendente_count': retention_action_counts.get('Pendente', 0),
        'nao_retido_count': final_outcome_counts.get('Nao Retido', 0),
    }

    output_path = PROJECT_ROOT / 'scripts' / 'validate_excel_structure_report.json'
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'VALIDATION_STRUCTURE_REPORT_WRITTEN {output_path}')


if __name__ == '__main__':
    main()
