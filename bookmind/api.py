from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .services import Services, create_services

UserId = Path(..., pattern=r"^[A-Za-z0-9_\-]{1,64}$")


class ChatRequest(BaseModel):
    user_id: str = Field(..., pattern=r"^[A-Za-z0-9_\-]{1,64}$")
    message: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str]


class LibraryItemIn(BaseModel):
    book_id: str
    status: Literal["okudum", "okuyorum", "okuyacagim"] = "okudum"
    rating: int | None = Field(default=None, ge=1, le=5)


def create_app(services: Services | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = services or create_services()
        yield

    app = FastAPI(
        title="BookMind API",
        version="2.0.0",
        description="Kisisel kutuphaneye gore Turkce kitap onerisi yapan agent servisi.",
        lifespan=lifespan,
    )

    def get_services(request: Request) -> Services:
        return request.app.state.services

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, s: Services = Depends(get_services)):
        result = await run_in_threadpool(s.agent.chat, body.user_id, body.message)
        return ChatResponse(reply=result.reply, tools_used=result.tools_used)

    @app.delete("/chat/{user_id}")
    def reset_chat(user_id: str = UserId, s: Services = Depends(get_services)):
        s.agent.reset(user_id)
        return {"reset": True}

    @app.get("/books/search")
    def search_books(
        q: str = Query(..., min_length=2, max_length=200),
        limit: int = Query(5, ge=1, le=20),
        s: Services = Depends(get_services),
    ):
        hits = s.store.search(q, k=limit)
        books = s.db.get_books([book_id for book_id, _ in hits])
        return [
            {**books[book_id], "score": round(score, 4)} for book_id, score in hits if book_id in books
        ]

    @app.get("/books/{book_id}")
    def get_book(book_id: str, s: Services = Depends(get_services)):
        book = s.db.get_book(book_id)
        if book is None:
            raise HTTPException(404, "Kitap bulunamadi")
        return book

    @app.get("/users/{user_id}/library")
    def get_library(user_id: str = UserId, s: Services = Depends(get_services)):
        return s.db.get_library(user_id)

    @app.post("/users/{user_id}/library", status_code=201)
    def add_to_library(item: LibraryItemIn, user_id: str = UserId, s: Services = Depends(get_services)):
        try:
            s.db.add_to_library(user_id, item.book_id, item.status, item.rating)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"added": item.book_id}

    @app.delete("/users/{user_id}/library/{book_id}")
    def remove_from_library(book_id: str, user_id: str = UserId, s: Services = Depends(get_services)):
        if not s.db.remove_from_library(user_id, book_id):
            raise HTTPException(404, "Kitap kutuphanede yok")
        return {"removed": book_id}

    return app


app = create_app()
