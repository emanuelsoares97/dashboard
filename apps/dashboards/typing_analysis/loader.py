import functools
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from .normalizer import extract_keywords, normalize_text
from .keyword_defaults import get_boost_keywords

DATA_FILE = Path(__file__).parent.parent / 'data' / 'tip_descricao.xlsx'


@dataclass
class TypificationDefinition:
    category: str
    subcategory: str
    third_category: str
    utilizacao: str
    keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)

    @property
    def full_path(self) -> str:
        parts = [p for p in [self.category, self.subcategory, self.third_category] if p]
        return ' / '.join(parts)

    @property
    def all_text(self) -> str:
        return ' '.join([self.category, self.subcategory, self.third_category, self.utilizacao])


def _forward_fill(value, last: str) -> tuple[str, str]:
    """Devolve (atual, ultimo_preenchido). Propaga o valor anterior quando a célula está vazia."""
    if value is None or str(value).strip() == '':
        return last, last
    normalized = normalize_text(str(value))
    return normalized, normalized


@functools.lru_cache(maxsize=1)
def load_tipification_definitions() -> tuple[TypificationDefinition, ...]:
    """Carrega e guarda em cache as definições de tipificação a partir do ficheiro xlsx de referência."""
    if not DATA_FILE.exists():
        return ()

    wb = openpyxl.load_workbook(DATA_FILE, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return ()

    # Avança até encontrar o cabeçalho (primeira linha com conteúdo na coluna 1)
    data_start = 0
    for i, row in enumerate(rows):
        if row and row[1] is not None and str(row[1]).strip():
            data_start = i + 1  # linha a seguir ao cabeçalho
            break

    definitions: list[TypificationDefinition] = []
    last_cat1 = ''
    last_cat2 = ''

    for row in rows[data_start:]:
        if not row or all(cell is None for cell in row):
            continue

        cat1_raw = row[1] if len(row) > 1 else None
        cat2_raw = row[2] if len(row) > 2 else None
        cat3_raw = row[3] if len(row) > 3 else None
        utilizacao_raw = row[4] if len(row) > 4 else None

        cat1, last_cat1 = _forward_fill(cat1_raw, last_cat1)
        cat2, last_cat2 = _forward_fill(cat2_raw, last_cat2)
        cat3 = normalize_text(str(cat3_raw)) if cat3_raw is not None and str(cat3_raw).strip() else ''
        utilizacao = normalize_text(str(utilizacao_raw)) if utilizacao_raw is not None else ''

        if not cat3:
            continue  # tipificação folha obrigatória

        kw_source = ' '.join([cat1, cat2, cat3, utilizacao])
        keywords = extract_keywords(kw_source) + get_boost_keywords(cat3)
        # Deduplica mantendo a ordem de inserção
        seen: set[str] = set()
        deduped_keywords: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                deduped_keywords.append(kw)

        definitions.append(TypificationDefinition(
            category=cat1,
            subcategory=cat2,
            third_category=cat3,
            utilizacao=utilizacao,
            keywords=deduped_keywords,
        ))

    return tuple(definitions)
