import re
import unicodedata


def normalize_label(value: str | None) -> str:
    """Normaliza labels para comparação robusta entre fontes reais."""
    if not value:
        return ''

    normalized = unicodedata.normalize('NFKD', value)
    normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def build_normalized_set(values: set[str]) -> set[str]:
    """Devolve conjunto já normalizado para comparações rápidas."""
    return {normalize_label(value) for value in values if normalize_label(value)}


def is_label_in(value: str | None, normalized_values: set[str]) -> bool:
    """Compara um valor com um conjunto de valores normalizados."""
    return normalize_label(value) in normalized_values
