"""Model cagirmaya gerek olmayan kisa mesajlar icin hazir cevaplar.

Sadece mesajin tamami bir selamlama veya tesekkurden olusuyorsa devreye girer.
"merhaba, polisiye onerir misin" gibi mesajlar agent'a gider.
"""

import re

from .text import normalize

_RULES = [
    (
        r"(merhaba|selam|selamlar|selamun aleykum|hey|hi|hello|gunaydin|iyi gunler|iyi aksamlar)",
        "Merhaba! Ne tur bir kitap ariyorsunuz? Bir konu, tur ya da sevdiginiz bir kitabi "
        "soylerseniz ona gore oneri yapabilirim.",
    ),
    (
        r"(tesekkurler|tesekkur ederim|tesekkurlar|sagol|sag ol|cok sagol|eyvallah|thanks|thank you)",
        "Rica ederim! Baska bir oneri isterseniz buradayim.",
    ),
]

_COMPILED = [
    (re.compile(rf"^(?:{pattern})(?:\s+(?:claude|bookmind))?[\s!.,?]*$"), reply)
    for pattern, reply in _RULES
]


def quick_reply(message: str) -> str | None:
    text = normalize(message)
    for pattern, reply in _COMPILED:
        if pattern.match(text):
            return reply
    return None
