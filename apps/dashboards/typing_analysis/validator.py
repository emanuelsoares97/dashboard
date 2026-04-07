from dataclasses import dataclass

from .loader import TypificationDefinition, load_tipification_definitions
from .normalizer import normalize_text
from .scorer import RankedResult, ScoreBreakdown, score_all, score_typification

STATUS_CORRECT = 'correct'
STATUS_LIKELY_CORRECT = 'likely_correct'
STATUS_NEEDS_REVIEW = 'needs_review'
STATUS_LIKELY_INCORRECT = 'likely_incorrect'
STATUS_INSUFFICIENT = 'insufficient_info'
STATUS_EMPTY = 'empty'
STATUS_BLANK_TYPIFICATION = 'blank_typification'

STATUS_LABELS: dict[str, str] = {
    STATUS_CORRECT: 'Correto',
    STATUS_LIKELY_CORRECT: 'Provável correto',
    STATUS_NEEDS_REVIEW: 'Requer revisão',
    STATUS_LIKELY_INCORRECT: 'Provável incorreto',
    STATUS_INSUFFICIENT: 'Info. insuficiente',
    STATUS_EMPTY: 'Observação vazia',
    STATUS_BLANK_TYPIFICATION: 'Tipificação em branco',
}

STATUS_CSS: dict[str, str] = {
    STATUS_CORRECT: 'badge-good',
    STATUS_LIKELY_CORRECT: 'badge-info',
    STATUS_NEEDS_REVIEW: 'badge-warning',
    STATUS_LIKELY_INCORRECT: 'badge-critical',
    STATUS_INSUFFICIENT: 'badge-neutral',
    STATUS_EMPTY: 'badge-neutral',
    STATUS_BLANK_TYPIFICATION: 'badge-warning',
}

_MIN_WORDS = 4


@dataclass
class ValidationResult:
    status: str
    status_label: str
    status_css: str
    used_score: float
    best_score: float
    best_path: str
    delta: float
    reason: str
    suggestion: str | None


def _find_used_definition(
    category: str,
    subcategory: str,
    third_category: str,
    definitions: tuple[TypificationDefinition, ...],
) -> TypificationDefinition | None:
    cat_n = normalize_text(category)
    sub_n = normalize_text(subcategory)
    third_n = normalize_text(third_category)

    # Correspondência exacta nos três níveis
    for defn in definitions:
        if (
            defn.category == cat_n
            and defn.subcategory == sub_n
            and defn.third_category == third_n
        ):
            return defn

    # Fallback: correspondência apenas no third_category
    for defn in definitions:
        if defn.third_category == third_n:
            return defn

    return None


def _empty_result() -> ValidationResult:
    return ValidationResult(
        status=STATUS_EMPTY,
        status_label=STATUS_LABELS[STATUS_EMPTY],
        status_css=STATUS_CSS[STATUS_EMPTY],
        used_score=0.0,
        best_score=0.0,
        best_path='',
        delta=0.0,
        reason='A observação está vazia.',
        suggestion=None,
    )


def _insufficient_result() -> ValidationResult:
    return ValidationResult(
        status=STATUS_INSUFFICIENT,
        status_label=STATUS_LABELS[STATUS_INSUFFICIENT],
        status_css=STATUS_CSS[STATUS_INSUFFICIENT],
        used_score=0.0,
        best_score=0.0,
        best_path='',
        delta=0.0,
        reason='Observação demasiado curta para análise.',
        suggestion=None,
    )


def _blank_typification_result() -> ValidationResult:
    return ValidationResult(
        status=STATUS_BLANK_TYPIFICATION,
        status_label=STATUS_LABELS[STATUS_BLANK_TYPIFICATION],
        status_css=STATUS_CSS[STATUS_BLANK_TYPIFICATION],
        used_score=0.0,
        best_score=0.0,
        best_path='',
        delta=0.0,
        reason='Falta preencher pelo menos um dos níveis da tipificação.',
        suggestion=None,
    )


def validate(
    observations: str,
    category: str,
    subcategory: str,
    third_category: str,
    *,
    definitions: tuple[TypificationDefinition, ...] | None = None,
) -> ValidationResult:
    if definitions is None:
        definitions = load_tipification_definitions()

    if not category.strip() or not subcategory.strip() or not third_category.strip():
        return _blank_typification_result()

    if not observations or not observations.strip():
        return _empty_result()

    obs_normalized = normalize_text(observations)

    if len(obs_normalized.split()) < _MIN_WORDS:
        return _insufficient_result()

    if not definitions:
        return ValidationResult(
            status=STATUS_NEEDS_REVIEW,
            status_label=STATUS_LABELS[STATUS_NEEDS_REVIEW],
            status_css=STATUS_CSS[STATUS_NEEDS_REVIEW],
            used_score=0.0,
            best_score=0.0,
            best_path='',
            delta=0.0,
            reason='Sem definições de tipificação carregadas.',
            suggestion=None,
        )

    ranked: list[RankedResult] = score_all(obs_normalized, definitions)
    best = ranked[0] if ranked else None
    best_score = best.score.total if best else 0.0
    best_path = best.definition.full_path if best else ''

    used_defn = _find_used_definition(category, subcategory, third_category, definitions)

    if used_defn is None:
        used_score = 0.0
        reason_prefix = f'Tipificação não reconhecida no ficheiro de referência ({third_category or "—"}). '
    else:
        sb: ScoreBreakdown = score_typification(obs_normalized, used_defn)
        used_score = sb.total
        reason_prefix = ''

    delta = max(0.0, best_score - used_score)

    if used_score >= 0.60 and delta < 0.15:
        status = STATUS_CORRECT
        reason = reason_prefix + 'Observação alinhada com a tipificação utilizada.'
        suggestion = None
    elif used_score >= 0.40 and delta < 0.25:
        status = STATUS_LIKELY_CORRECT
        reason = reason_prefix + 'Observação parcialmente alinhada com a tipificação.'
        suggestion = best_path if delta > 0.10 else None
    elif used_score < 0.30 or (delta > 0.30 and best_score > 0.50):
        status = STATUS_LIKELY_INCORRECT
        reason = (
            reason_prefix
            or f'Observação sugere tipificação diferente (score usado: {used_score:.2f}; melhor: {best_score:.2f}).'
        )
        suggestion = best_path
    else:
        status = STATUS_NEEDS_REVIEW
        reason = reason_prefix + f'Alinhamento inconclusivo (score: {used_score:.2f}; delta: {delta:.2f}).'
        suggestion = best_path if delta > 0.15 else None

    return ValidationResult(
        status=status,
        status_label=STATUS_LABELS[status],
        status_css=STATUS_CSS[status],
        used_score=round(used_score, 3),
        best_score=round(best_score, 3),
        best_path=best_path,
        delta=round(delta, 3),
        reason=reason,
        suggestion=suggestion,
    )
