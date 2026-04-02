from apps.imports_app.types import ImportRowData, QualityFlagInput
from apps.quality.models import DataQualityFlag


def detect_inconsistencies(row_data: ImportRowData) -> list[QualityFlagInput]:
    flags: list[QualityFlagInput] = []

    if row_data.resolution.lower() == 'pendente' and row_data.ret_resolution.lower() == 'retido':
        flags.append(
            QualityFlagInput(
                flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
                rule_code='pending_resolution_with_retained_outcome',
                severity=DataQualityFlag.Severity.WARNING,
                description='resolution=Pendente and Ret Resolution=Retido',
            )
        )

    return flags
