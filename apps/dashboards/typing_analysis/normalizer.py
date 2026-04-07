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


def normalize_text(text: str | None) -> str:
    """Converte texto para minúsculas, remove acentos e colapsa espaços."""
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(text).strip().lower())
    without_accents = ''.join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r'[^\w\s]', ' ', without_accents)
    return re.sub(r'\s+', ' ', cleaned).strip()


def extract_keywords(text: str) -> list[str]:
    """Extrai palavras com significado do texto, removendo stopwords."""
    words = normalize_text(text).split()
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]
