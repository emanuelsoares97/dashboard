from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ImportRowData:
    row_number: int
    raw_payload: dict[str, Any]
    external_call_id: str
    agent_name: str
    start_at: datetime | None
    end_at: datetime | None
    final_outcome: str
    retention_action: str
    churn_reason: str
    service_type: str
    is_call_drop: bool
    day: str
    week: str
    month: str
    exclude: str
    category: str = ''
    subcategory: str = ''
    observations: str = ''
    direction: str = 'inbound'


@dataclass(slots=True)
class QualityFlagInput:
    flag_type: str
    rule_code: str
    severity: str
    description: str


@dataclass(slots=True)
class RowValidationResult:
    row_data: ImportRowData
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(slots=True)
class ImportSummary:
    total_rows: int = 0
    imported_rows: int = 0
    skipped_non_retention_rows: int = 0
    consolidated_existing_rows: int = 0
    failed_rows: int = 0
    duplicate_rows: int = 0
    duplicate_in_file_rows: int = 0
    duplicate_previous_rows: int = 0
    inconsistencies: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            'total_rows': self.total_rows,
            'imported_rows': self.imported_rows,
            'skipped_non_retention_rows': self.skipped_non_retention_rows,
            'consolidated_existing_rows': self.consolidated_existing_rows,
            'failed_rows': self.failed_rows,
            'duplicate_rows': self.duplicate_rows,
            'duplicate_in_file_rows': self.duplicate_in_file_rows,
            'duplicate_previous_rows': self.duplicate_previous_rows,
            'inconsistencies': self.inconsistencies,
        }
