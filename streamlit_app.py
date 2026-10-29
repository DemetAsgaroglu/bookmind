"""BookMind icin Streamlit arayuzu: sohbet, anlamsal arama ve kisisel kutuphane.

Calistirma: streamlit run streamlit_app.py
"""

import streamlit as st

from bookmind.database import LIBRARY_STATUSES
from bookmind.services import create_services

st.set_page_config(page_title="BookMind", page_icon=":books:", layout="wide")


@st.cache_resource(show_spinner="Model ve indeks yukleniyor...")
def get_services():
    # Agent'in sohbet gecmisi bellekte tutuldugu icin servisler tum oturumlarda paylasilir
    return create_services(with_agent=True)


def book_card(book: dict, score: float | None = None) -> None:
    cover, info = st.columns([1, 5])
    if book.get("cover_url"):
        cover.image(book["cover_url"], width=80)
    meta = [book.get("author") or "", book.get("genre") or ""]
    if book.get("price") is not None:
        meta.append(f"{book['price']} TL")
    if score is not None:
        meta.append(f"benzerlik {score:.2f}")
    info.markdown(f"**{book['title']}**  \n{' · '.join(m for m in meta if m)}  \n`{book['id']}`")
    if book.get("description"):
        info.caption(book["description"][:300] + ("..." if len(book["description"]) > 300 else ""))


try:
    services = get_services()
except Exception as exc:  # noqa: BLE001 - kurulum eksikse sayfa bos kalmasin
    st.error(f"Servisler baslatilamadi: {exc}")
    st.stop()

with st.sidebar:
    st.title("BookMind")
    user_id = st.text_input("Kullanici", value="demet").strip() or "demo"
    debug = st.toggle("Arac cagrilarini goster", value=False)
    if st.button("Sohbeti sifirla"):
        services.agent.reset(user_id)
        st.session_state.pop(f"history_{user_id}", None)
        st.rerun()

chat_tab, search_tab, library_tab = st.tabs(["Sohbet", "Arama", "Kutuphanem"])

with chat_tab:
    history_key = f"history_{user_id}"
    history = st.session_state.setdefault(history_key, [])
    for item in history:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if debug and item.get("tool_calls"):
                for call in item["tool_calls"]:
                    st.code(f"{call['name']} {call['args']}", language="text")

    if message := st.chat_input("Ornek: En ucuz 3 bilim kurgu kitabi hangileri?"):
        history.append({"role": "user", "content": message})
        with st.chat_message("user"):
            st.markdown(message)
        with st.chat_message("assistant"):
            with st.spinner("Dusunuyor..."):
                try:
                    result = services.agent.chat(user_id, message)
                    reply, tool_calls = result.reply, result.tool_calls
                except Exception as exc:  # noqa: BLE001 - API hatasinda sohbet kapanmasin
                    reply, tool_calls = f"Hata: {exc}", []
            st.markdown(reply)
            if debug:
                for call in tool_calls:
                    st.code(f"{call['name']} {call['args']}", language="text")
        history.append({"role": "assistant", "content": reply, "tool_calls": tool_calls})

with search_tab:
    query = st.text_input("Konu, tema veya atmosfer", placeholder="uzayda gecen karanlik bir hikaye")
    limit = st.slider("Sonuc sayisi", 1, 20, 5)
    if query.strip():
        hits = services.store.search(query, k=limit)
        books = services.db.get_books([book_id for book_id, _ in hits])
        for book_id, score in hits:
            if book_id in books:
                book_card(books[book_id], score)
                st.divider()

with library_tab:
    with st.form("add_book", clear_on_submit=True):
        st.subheader("Kitap ekle")
        col1, col2, col3 = st.columns([3, 2, 1])
        book_id = col1.text_input("Kitap kimligi", placeholder="book_064")
        status = col2.selectbox("Durum", LIBRARY_STATUSES)
        rating = col3.selectbox("Puan", [None, 1, 2, 3, 4, 5])
        if st.form_submit_button("Ekle") and book_id.strip():
            try:
                services.db.add_to_library(user_id, book_id.strip(), status, rating)
                st.success("Eklendi.")
            except (KeyError, ValueError) as exc:
                st.error(str(exc))

    items = services.db.get_library(user_id)
    if not items:
        st.info("Kutuphaneniz bos. Arama sekmesinden kitap kimligini bulup ekleyebilirsiniz.")
    for item in items:
        col1, col2 = st.columns([6, 1])
        stars = " " + "★" * item["rating"] if item["rating"] else ""
        col1.markdown(f"**{item['title']}** ({item['author']}) · {item['status']}{stars}  \n`{item['id']}`")
        if col2.button("Cikar", key=f"remove_{item['id']}"):
            services.db.remove_from_library(user_id, item["id"])
            st.rerun()
