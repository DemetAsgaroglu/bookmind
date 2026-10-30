# BookMind - Kitap Öneri Asistanı

Bu proje, kullanıcının okuduğu kitaplara ve sorusuna göre Türkçe kitap önerisi yapan bir sohbet asistanıdır. Asistan, Gemini (veya Ollama ile yerel bir model) kullanarak soruyu anlar ve cevabı sadece katalogdaki kitaplardan üretir.

**Canlı demo:** https://bookmind-k9ge2eh5sakoshkgjnojup.streamlit.app/

Örnek sorular:
- "Okuduğum kitaplara benzer bir roman öner"
- "150 TL altındaki polisiyeler neler?"
- "Uzayda geçen karanlık bir hikaye arıyorum"

## Proje Hakkında

Projenin ilk sürümünü bir hackathon için ASP.NET Core ve Firebase ile geliştirmiştim. Bu sürümde projeyi Python ile baştan yazdım ve tek adımlı RAG yapısını, araç kullanabilen bir agent'a dönüştürdüm.

Agent, soruya göre hangi aracı kullanacağına kendisi karar verir:
- **search_books:** Konu, tema veya atmosfere göre anlamsal arama (FAISS + çok dilli embedding modeli)
- **query_catalog:** Fiyat, yazar, tür, sayma gibi kesin sorular için SQL sorgusu (Text-to-SQL)
- **get_my_library:** Kullanıcının kişisel kütüphanesi (okudum / okuyorum / okuyacağım ve 1-5 puan)

Modelin yazdığı SQL sorguları doğrudan çalıştırılmaz. Sadece `books` tablosundan okuma yapabilen, salt okunur bir bağlantıda çalıştırılır. Böylece model başka kullanıcıların kütüphanesine erişemez veya veritabanını değiştiremez.

### Öne Çıkan Özellikler
- Okunan kitaplar tekrar önerilmez.
- Türkçe karakter olmadan yazılan sorular da doğru çalışır ("siir kitabi" ile "şiir kitabı" aynı sonucu verir).
- Gemini yoğun olduğunda veya kota dolduğunda istek otomatik olarak yedek modele geçer.
- Streamlit arayüzü, FastAPI servisi ve komut satırı ile kullanılabilir.

## Veri Seti

Katalog, Google Books API'den Türkçe açıklaması olan kitaplar toplanarak oluşturuldu (`scripts/fetch_books.py`). Tekrar eden ve açıklaması çok kısa olan kitaplar temizlendikten sonra **536 kitap** kaldı. Fiyatlar örnek veri olarak rastgele atanmıştır.

## Değerlendirme

Sistemi ölçmek için iki test seti hazırladım:
- **Arama (25 sorgu):** İlk 5 sonuçta beklenen türden kitap var mı?
- **Agent (18 soru):** Doğru aracı seçiyor mu? SQL gerektiren 10 soruda cevap doğru mu?

| Ölçüm | Sonuç |
| :--- | :--- |
| Arama - Hit@5 | %88 |
| Arama - Precision@5 | %57,6 |
| Agent - Doğru araç seçimi | %100 (18/18) |
| Agent - SQL cevap doğruluğu | %90 (9/10) |

Agent ölçümü Gemini 3.1 Flash Lite ile yapıldı. Arama test setindeki sorgular bilerek Türkçe karakter olmadan yazıldı. İlk ölçümde Hit@5 %52 çıktı; sorgudaki kelimeleri katalogdan çıkarılan bir sözlükle düzelttikten sonra %88'e yükseldi.

## Proje Yapısı

```text
bookmind/
├── bookmind/
│   ├── agent.py          # LangGraph agent
│   ├── tools.py          # Agent'ın kullandığı araçlar
│   ├── sql_guard.py      # SQL sorgularının güvenli çalıştırılması
│   ├── vector_store.py   # FAISS ile anlamsal arama
│   ├── database.py       # SQLite: katalog ve kişisel kütüphane
│   ├── llm.py            # Gemini / Ollama seçimi
│   ├── api.py            # FastAPI
│   └── cli.py            # Komut satırı
├── scripts/              # Veri toplama, temizleme ve indeks oluşturma
├── eval/                 # Test setleri ve değerlendirme
├── tests/                # Birim testleri
├── data/                 # Kitap kataloğu
└── streamlit_app.py      # Web arayüzü
```

## Kurulum ve Kullanım

1. **Projeyi klonlayın:**
   ```bash
   git clone https://github.com/DemetAsgaroglu/bookmind.git
   cd bookmind
   ```
2. **Gerekli kütüphaneleri kurun:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **API anahtarını ekleyin:** `.env.example` dosyasını `.env` olarak kopyalayıp `GOOGLE_API_KEY` değerini girin. Gemini yerine yerel model kullanmak için `LLM_PROVIDER=ollama` yazmanız yeterli.
4. **Veritabanını ve arama indeksini oluşturun:**
   ```bash
   python scripts/build_index.py
   ```
5. **Uygulamayı çalıştırın:**
   ```bash
   streamlit run streamlit_app.py                    # Web arayüzü
   python -m bookmind.cli chat --user demet --debug  # Komut satırı
   uvicorn bookmind.api:app --reload                 # API (http://localhost:8000/docs)
   ```

Testler ve değerlendirme için:
```bash
pip install -r requirements-dev.txt
pytest
python eval/run_eval.py retrieval
python eval/run_eval.py agent
```

## Kullanılan Teknolojiler

- **LangGraph / LangChain:** Agent yapısı
- **Gemini API / Ollama:** Dil modeli
- **Sentence Transformers + FAISS:** Anlamsal arama
- **SQLite:** Katalog ve kişisel kütüphane
- **Streamlit, FastAPI:** Arayüz ve API
- **Pytest:** Testler
- **Docker:** Paketleme
