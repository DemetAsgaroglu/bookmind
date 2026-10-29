import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable

_TR_LOWER = str.maketrans({"I": "ı", "İ": "i"})
_FOLD = str.maketrans({"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"})


def normalize(text: str | None) -> str:
    """Turkce karakterleri sadelestirip kucuk harfe cevirir.

    "Ahmet ÜMİT" ve "ahmet umit" ayni sonucu verir. Hem kural eslestirmede
    hem de SQL tarafindaki norm() fonksiyonunda kullanilir.
    """
    if not text:
        return ""
    text = text.translate(_TR_LOWER).lower().translate(_FOLD)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip()


_WORD = re.compile(r"\w+")


def build_vocabulary(texts: Iterable[str]) -> dict[str, str]:
    """Sadelestirilmis kelime -> metinlerde en sik gecen Turkce yazilisi ("siir" -> "şiir")."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for text in texts:
        for word in _WORD.findall(text.translate(_TR_LOWER).lower()):
            counts[normalize(word)][word] += 1
    vocabulary = {}
    for key, forms in counts.items():
        best = forms.most_common(1)[0][0]
        # Zaten sade yazilan kelimeleri saklamaya gerek yok
        if best != key:
            vocabulary[key] = best
    return vocabulary


def restore_turkish_chars(text: str, vocabulary: dict[str, str]) -> str:
    """Turkce karakter kullanilmadan yazilmis kelimeleri sozlukteki yazilisiyla degistirir.

    Embedding modeli "siir kitabi" ile "şiir kitabı"yi farkli anlar; arama oncesi duzeltilir.
    Icinde zaten Turkce karakter olan veya sozlukte olmayan kelimelere dokunulmaz.
    """

    def fix(match: re.Match) -> str:
        word = match.group(0)
        return vocabulary.get(word.lower(), word) if word.isascii() else word

    return _WORD.sub(fix, text)
