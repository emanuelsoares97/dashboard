import re
from dataclasses import dataclass

from .loader import TypificationDefinition
from .normalizer import extract_keywords

WEIGHTS = {
    'keyword': 0.55,
    'pattern': 0.25,
    'description': 0.10,
    'structure': 0.10,
}


@dataclass
class ScoreBreakdown:
    keyword: float
    pattern: float
    description: float
    structure: float
    total: float


@dataclass
class RankedResult:
    definition: TypificationDefinition
    score: ScoreBreakdown


def _score_keywords(
    obs_words: set[str],
    keywords: list[str],
    neg_keywords: list[str],
) -> float:
    if not keywords:
        return 0.5  # neutro quando não há palavras-chave de referência

    matched = sum(1 for kw in keywords if kw in obs_words)
    # Corresponder 1 em 3 palavras-chave únicas = pontuação máxima
    positive = min(1.0, matched / max(1, len(keywords)) * 3)

    penalty = 0.0
    if neg_keywords:
        neg_matched = sum(1 for nk in neg_keywords if nk in obs_words)
        penalty = (neg_matched / len(neg_keywords)) * 0.5

    return max(0.0, positive - penalty)


def _score_patterns(obs_normalized: str, patterns: list[str]) -> float:
    if not patterns:
        return 0.5  # neutro

    matched = sum(
        1 for p in patterns if re.search(p, obs_normalized, re.IGNORECASE)
    )
    return min(1.0, matched / max(1, len(patterns)) * 2)


def _score_description(obs_words: set[str], path_words: set[str]) -> float:
    if not path_words:
        return 0.0
    if not obs_words:
        return 0.0
    intersection = obs_words & path_words
    union = obs_words | path_words
    return len(intersection) / len(union)


def _score_structure(obs_normalized: str) -> float:
    word_count = len(obs_normalized.split())
    # 15 palavras = pontuação máxima; proporcional abaixo
    return min(1.0, word_count / 15)


def score_typification(
    obs_normalized: str, defn: TypificationDefinition
) -> ScoreBreakdown:
    obs_words = set(extract_keywords(obs_normalized))
    path_words = set(extract_keywords(defn.all_text))

    kw = _score_keywords(obs_words, defn.keywords, defn.negative_keywords)
    pat = _score_patterns(obs_normalized, defn.patterns)
    desc = _score_description(obs_words, path_words)
    struct = _score_structure(obs_normalized)

    total = (
        kw * WEIGHTS['keyword']
        + pat * WEIGHTS['pattern']
        + desc * WEIGHTS['description']
        + struct * WEIGHTS['structure']
    )

    return ScoreBreakdown(
        keyword=round(kw, 3),
        pattern=round(pat, 3),
        description=round(desc, 3),
        structure=round(struct, 3),
        total=round(total, 3),
    )


def score_all(
    obs_normalized: str,
    definitions: tuple[TypificationDefinition, ...],
) -> list[RankedResult]:
    results = [
        RankedResult(definition=defn, score=score_typification(obs_normalized, defn))
        for defn in definitions
    ]
    return sorted(results, key=lambda r: r.score.total, reverse=True)
