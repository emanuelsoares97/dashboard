import re
import unicodedata

_STOPWORDS = frozenset({
    'a', 'ao', 'as', 'assim', 'com', 'como', 'da', 'das', 'de', 'do', 'dos',
    'e', 'ela', 'ele', 'em', 'essa', 'esse', 'esta', 'este', 'eu', 'foi',
    'há', 'ha', 'isso', 'mas', 'me', 'na', 'nao', 'nas', 'neste', 'nesta',
    'no', 'nos', 'o', 'onde', 'os', 'ou', 'para', 'pela', 'pelo', 'pelas',
    'pelos', 'por', 'que', 'quem', 'se', 'ser', 'seu', 'sua', 'tem',
    'tenho', 'ter', 'teu', 'to', 'um', 'uma', 'uns', 'umas', 'vai', 'voce',
    'ja', 'pois', 'so', 'mais', 'vez',
})

_MOJIBAKE_MARKERS = ('Ã', 'â', '�')

_MOJIBAKE_REPLACEMENTS = {
    'Ã¡': 'á',
    'Ã ': 'à',
    'Ã¢': 'â',
    'Ã£': 'ã',
    'Ã¤': 'ä',
    'Ã©': 'é',
    'Ãª': 'ê',
    'Ã­': 'í',
    'Ã³': 'ó',
    'Ã´': 'ô',
    'Ãµ': 'õ',
    'Ãº': 'ú',
    'Ã¼': 'ü',
    'Ã§': 'ç',
    'â€™': "'",
    'â€œ': '"',
    'â€“': '-',
    'â€”': '-',
    'â€¦': '...',
}


def repair_text_encoding(text: str | None) -> str:
    """Corrige texto com codificacao UTF-8 lida como latin-1/cp1252."""
    if not text:
        return ''

    raw = str(text)
    if not any(marker in raw for marker in _MOJIBAKE_MARKERS):
        return raw

    try:
        repaired = raw.encode('latin-1').decode('utf-8')
        return repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        fallback = raw
        for wrong, right in _MOJIBAKE_REPLACEMENTS.items():
            fallback = fallback.replace(wrong, right)
        return fallback


def normalize_text(text: str | None) -> str:
    """Converte texto para minúsculas, remove acentos e colapsa espaços."""
    if not text:
        return ''
    repaired = repair_text_encoding(text)
    nfkd = unicodedata.normalize('NFKD', repaired.strip().lower())
    without_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r'[^\w\s]', ' ', without_accents)
    return re.sub(r'\s+', ' ', cleaned).strip()


def extract_keywords(text: str) -> list[str]:
    """Extrai palavras com significado do texto, removendo stopwords."""
    words = normalize_text(text).split()
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]
