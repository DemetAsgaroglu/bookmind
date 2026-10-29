from fastapi.testclient import TestClient
from langchain_core.exceptions import ModelAPIError, ModelRateLimitError, ModelTimeoutError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from bookmind.agent import BUSY_REPLY, BookAgent
from bookmind.api import create_app
from bookmind.services import Services

from .conftest import tool_call


def test_agent_uses_tool_then_answers(db, store, scripted):
    llm = scripted(
        tool_call("query_catalog", {"sql": "SELECT id, title FROM books WHERE price < 100 LIMIT 3"}),
        AIMessage(content="Iste uygun fiyatli uc kitap."),
    )
    agent = BookAgent(llm, db, store)
    result = agent.chat("demet", "100 TL altinda kitap var mi?")

    assert result.reply == "Iste uygun fiyatli uc kitap."
    assert result.tools_used == ["query_catalog"]
    second_call = llm.calls[1]
    tool_outputs = [m for m in second_call if isinstance(m, ToolMessage)]
    assert tool_outputs and "book_" in tool_outputs[0].content


def test_history_is_separate_per_user(db, store, scripted):
    llm = scripted(AIMessage(content="cevap 1"), AIMessage(content="cevap 2"), AIMessage(content="cevap 3"))
    agent = BookAgent(llm, db, store)
    agent.chat("demet", "bilim kurgu sever misin")
    agent.chat("ali", "tarih kitabi oner")

    ali_messages = [m.content for m in llm.calls[1] if isinstance(m, HumanMessage)]
    assert ali_messages == ["tarih kitabi oner"]

    agent.chat("demet", "baska?")
    demet_messages = [m.content for m in llm.calls[2] if isinstance(m, HumanMessage)]
    assert demet_messages == ["bilim kurgu sever misin", "baska?"]


def test_reset_clears_history(db, store, scripted):
    llm = scripted(AIMessage(content="a"), AIMessage(content="b"))
    agent = BookAgent(llm, db, store)
    agent.chat("demet", "ilk soru")
    agent.reset("demet")
    agent.chat("demet", "ikinci soru")
    assert [m.content for m in llm.calls[1] if isinstance(m, HumanMessage)] == ["ikinci soru"]


def test_greeting_skips_llm(db, store, scripted):
    llm = scripted()
    agent = BookAgent(llm, db, store)
    assert "kitap" in agent.chat("demet", "Merhaba").reply
    assert llm.calls == []


def test_step_limit_returns_fallback(db, store, scripted):
    looping = [tool_call("get_my_library", {}, call_id=f"c{i}") for i in range(10)]
    agent = BookAgent(scripted(*looping), db, store, max_steps=2)
    result = agent.chat("demet", "sonsuz dongu")
    assert "cevaplayamadim" in result.reply


def test_api_endpoints(db, store, scripted):
    llm = scripted(AIMessage(content="Merak ettiginiz kitap burada."))
    services = Services(db=db, store=store, agent=BookAgent(llm, db, store))
    with TestClient(create_app(services)) as client:
        assert client.get("/health").json() == {"status": "ok"}

        r = client.post("/users/demet/library", json={"book_id": "book_003", "rating": 5})
        assert r.status_code == 201
        assert client.get("/users/demet/library").json()[0]["id"] == "book_003"
        assert client.post("/users/demet/library", json={"book_id": "yok"}).status_code == 404
        assert client.post("/users/demet/library", json={"book_id": "book_003", "rating": 9}).status_code == 422

        r = client.post("/chat", json={"user_id": "demet", "message": "bir roman oner"})
        assert r.json()["reply"] == "Merak ettiginiz kitap burada."

        assert len(client.get("/books/search", params={"q": "bilim kurgu", "limit": 3}).json()) == 3
        assert client.get("/books/book_001").status_code == 200
        assert client.delete("/users/demet/library/book_003").status_code == 200
        assert client.post("/chat", json={"user_id": "../etc", "message": "x"}).status_code == 422


def test_fallback_model_used_when_primary_is_busy(db, store, scripted):
    primary = scripted(ModelAPIError("503 UNAVAILABLE"))
    fallback = scripted(AIMessage(content="yedek modelden cevap"))
    agent = BookAgent(primary, db, store, fallback_llms=[fallback])
    assert agent.chat("demet", "bir roman oner").reply == "yedek modelden cevap"
    assert len(primary.calls) == 1 and len(fallback.calls) == 1


def test_busy_reply_when_all_models_fail(db, store, scripted):
    primary = scripted(ModelAPIError("503 UNAVAILABLE"))
    fallback = scripted(ModelTimeoutError("504 DEADLINE_EXCEEDED"))
    agent = BookAgent(primary, db, store, fallback_llms=[fallback])
    assert agent.chat("demet", "bir roman oner").reply == BUSY_REPLY


def test_failed_model_is_skipped_on_next_steps(db, store, scripted):
    primary = scripted(ModelRateLimitError("429 RESOURCE_EXHAUSTED"))
    fallback = scripted(
        tool_call("query_catalog", {"sql": "SELECT title FROM books LIMIT 1"}),
        AIMessage(content="cevap"),
        AIMessage(content="ikinci cevap"),
    )
    agent = BookAgent(primary, db, store, fallback_llms=[fallback])
    assert agent.chat("demet", "en ucuz kitap").reply == "cevap"
    assert agent.chat("demet", "baska bir soru").reply == "ikinci cevap"
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 3
