from pathlib import Path
import argparse
import json
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402


django.setup()

from apps.imports_app.parsers.excel_reader import iter_row_payloads  # noqa: E402
from apps.imports_app.parsers.excel_reader import read_excel_dataframe  # noqa: E402
from apps.imports_app.parsers.row_mapper import map_row  # noqa: E402
from apps.inbound.models import Interaction  # noqa: E402
from apps.dashboards.services.label_normalization import normalize_label  # noqa: E402


def _top_counts(values: dict[str, int], limit: int = 50):
    return sorted(values.items(), key=lambda item: item[1], reverse=True)[:limit]


def _collect_from_excel(file_path: Path) -> dict:
    outcome_counts = {}
    action_counts = {}

    dataframe = read_excel_dataframe(file_path)
    for row_number, row_payload in iter_row_payloads(dataframe):
        row = map_row(row_number, row_payload)

        outcome = row.final_outcome.strip() if row.final_outcome else ''
        action = row.retention_action.strip() if row.retention_action else ''

        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        action_counts[action] = action_counts.get(action, 0) + 1

    return {
        'source': str(file_path),
        'total_rows': len(dataframe),
        'outcome_labels': _top_counts(outcome_counts),
        'outcome_labels_normalized': _top_counts({normalize_label(k): v for k, v in outcome_counts.items()}),
        'retention_action_labels': _top_counts(action_counts),
        'retention_action_labels_normalized': _top_counts({normalize_label(k): v for k, v in action_counts.items()}),
    }


def _collect_from_database() -> dict:
    outcome_counts = {}
    action_counts = {}

    for label in Interaction.objects.values_list('final_outcome__label', flat=True):
        value = (label or '').strip()
        outcome_counts[value] = outcome_counts.get(value, 0) + 1

    for label in Interaction.objects.values_list('retention_action__label', flat=True):
        value = (label or '').strip()
        action_counts[value] = action_counts.get(value, 0) + 1

    return {
        'source': 'database',
        'total_rows': Interaction.objects.count(),
        'outcome_labels': _top_counts(outcome_counts),
        'outcome_labels_normalized': _top_counts({normalize_label(k): v for k, v in outcome_counts.items()}),
        'retention_action_labels': _top_counts(action_counts),
        'retention_action_labels_normalized': _top_counts({normalize_label(k): v for k, v in action_counts.items()}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Diagnóstico de labels (outcome e retention_action).')
    parser.add_argument('--excel', type=str, default='tip ret (2).xlsx', help='Caminho do Excel para diagnóstico.')
    parser.add_argument('--output', type=str, default='scripts/diagnose_labels_report.json', help='Ficheiro JSON de saída.')
    args = parser.parse_args()

    excel_path = Path(args.excel)
    if not excel_path.is_absolute():
        excel_path = PROJECT_ROOT / excel_path

    report = {
        'excel': _collect_from_excel(excel_path),
        'database': _collect_from_database(),
    }

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'DIAGNOSE_LABELS_REPORT_WRITTEN {output_path}')


if __name__ == '__main__':
    main()
