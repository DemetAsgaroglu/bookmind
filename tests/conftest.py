import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bookmind.database import Database  # noqa: E402
from bookmind.text import normalize  # noqa: E402
from bookmind.vector_store import VectorStore  # noqa: E402

CATALOG = ROOT / "data" / "books_cleaned.json"


class HashEmbedder:
    """Testlerde model indirmeden calismak icin basit kelime-torbasi embedder."""

    dim = 256

    def encode(self, texts):
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for row, text in enumerate(texts):
            for token in normalize(text).split():
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                out[row, h % self.dim] += 1.0
        return out


class ScriptedChatModel(BaseChatModel):
    """Sirayla onceden belirlenmis mesajlari donduren sahte model."""

    responses: list
    calls: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        message = self.responses.pop(0)
        if isinstance(message, Exception):
            raise message
        return ChatResult(generations=[ChatGeneration(message=message)])


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.load_catalog(CATALOG)
    return database


@pytest.fixture
def store(db):
    return VectorStore.build(db.all_books(), HashEmbedder())


def tool_call(name, args, call_id="call_1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture
def scripted():
    def make(*responses):
        return ScriptedChatModel(responses=list(responses), calls=[])

    return make
