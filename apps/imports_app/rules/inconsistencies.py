from apps.imports_app.types import ImportRowData, QualityFlagInput
from apps.quality.models import DataQualityFlag

# Labels de outcome que nunca devem aparecer como retention_action.
# Valores normalizados (lowercase, stripped) para comparacao case-insensitive.
_OUTCOME_DOMAIN_NORMALIZED: frozenset[str] = frozenset({
    'retido',
    'nao retido',
    'nao retida',
    'call drop',
    'calldrop',
})


def detect_inconsistencies(row_data: ImportRowData) -> list[QualityFlagInput]:
    flags: list[QualityFlagInput] = []

    if row_data.retention_action.lower() == 'pendente' and row_data.final_outcome.lower() == 'retido':
        flags.append(
            QualityFlagInput(
                flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
                rule_code='pending_resolution_with_retained_outcome',
                severity=DataQualityFlag.Severity.WARNING,
                description='resolution=Pendente and Ret Resolution=Retido',
            )
        )

    normalized_action = row_data.retention_action.strip().lower()
    if normalized_action in _OUTCOME_DOMAIN_NORMALIZED:
        flags.append(
            QualityFlagInput(
                flag_type=DataQualityFlag.FlagType.TIPIFICATION_INCONSISTENCY,
                rule_code='outcome_value_in_retention_action',
                severity=DataQualityFlag.Severity.ERROR,
                description=(
                    f'retention_action="{row_data.retention_action}" parece ser um outcome, '
                    f'nao uma acao de retencao.'
                ),
            )
        )

    return flags
