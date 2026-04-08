from pathlib import Path
from datetime import timedelta
import os
import sys
import json
import warnings

import django


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.imports_app.models import ImportBatch  # noqa: E402
from apps.imports_app.services import import_excel  # noqa: E402
from apps.inbound.models import Interaction  # noqa: E402
from apps.dashboards.services.previous_day import build_previous_day_payload  # noqa: E402


warnings.filterwarnings('ignore', category=RuntimeWarning)


def main() -> None:
    file_path = Path('tip ret (2).xlsx')
    if not file_path.exists():
        raise FileNotFoundError(f'Ficheiro nao encontrado: {file_path}')

    batch = ImportBatch.objects.create(
        original_filename=file_path.name,
        stored_filename=file_path.name,
    )
    summary = import_excel(file_path, batch)
    batch.refresh_from_db()

    report = {
        'summary': summary,
        'batch_status': batch.status,
        'total_rows': batch.total_rows,
        'success_rows': batch.success_rows,
        'failed_rows': batch.failed_rows,
        'duplicate_rows': batch.duplicate_rows,
        'flagged_rows': batch.flagged_rows,
        'error_log_head': (batch.error_log or '')[:2500],
        'imported_interactions': 0,
        'date_range': None,
        'previous_day_total_calls': 0,
        'previous_day_audit_calls': 0,
        'top_audit_call': None,
        'top_audit_score': None,
        'top_audit_reasons': [],
        'retention_action_labels_sample': [],
    }

    imported_qs = Interaction.objects.filter(source_row__batch=batch)
    report['imported_interactions'] = imported_qs.count()

    if imported_qs.exists():
        min_day = imported_qs.order_by('occurred_on').first().occurred_on
        max_day = imported_qs.order_by('-occurred_on').first().occurred_on
        report['date_range'] = [min_day.isoformat(), max_day.isoformat()]

        payload = build_previous_day_payload({}, reference_date=max_day + timedelta(days=1))
        report['previous_day_total_calls'] = payload['kpis']['total_calls']
        report['previous_day_audit_calls'] = len(payload['audit_calls'])

        if payload['audit_calls']:
            top = payload['audit_calls'][0]
            report['top_audit_call'] = top['call_id_external']
            report['top_audit_score'] = top['audit_priority_score']
            report['top_audit_reasons'] = top['audit_reasons']

        labels = list(imported_qs.values_list('retention_action__label', flat=True).distinct()[:50])
        report['retention_action_labels_sample'] = labels

    output_path = PROJECT_ROOT / 'scripts' / 'validate_report.json'
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'VALIDATION_REPORT_WRITTEN {output_path}')


if __name__ == '__main__':
    main()
