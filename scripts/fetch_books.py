import os
import json
import random
import requests
import time
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")

os.makedirs("data", exist_ok=True)

CATEGORIES = [
    "Çocuk Kitapları", "Tarihi Roman", "Aşk Romanları", "Bilgisayar Programlama",
    "Ekonomi ve Finans", "Sanat Tarihi", "Müzik", "Gezi Rehberi", "Sağlık ve Tıp",
    "Spor", "Hukuk", "Siyaset", "Eğitim Bilimleri", "Mühendislik",
    "Din", "Mizah", "Şiir", "Tiyatro", "Deneme", "Sosyoloji"
]

def fetch_books():
    books_data = []
    book_counter = 1
    output_file = os.path.join("data", "books.json")
    
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            raw_books = json.load(f)
            tr_chars = set("ğüşıöçĞÜŞİÖÇ")
            books_data = [b for b in raw_books if any(c in b.get("description", "") for c in tr_chars)]
            
            # ID'leri yeniden sırala
            for i, book in enumerate(books_data):
                book["id"] = f"book_{i+1:03d}"
                
            book_counter = len(books_data) + 1
            print(f"İngilizce kitaplar temizlendi. Kalan saf Türkçe kitap: {len(books_data)}. Üzerine ekleme yapılıyor...")
    category_counts = {cat: 0 for cat in CATEGORIES}

    print("Google Books API'den kitap verileri çekiliyor...\n")

    for category in CATEGORIES:
        print(f"'{category}' kategorisi için kitaplar aranıyor...")
        collected_for_category = 0
        start_index = 0
        
        # Her kategori için 50 kitaba ulaşana kadar sayfaları gez (maksimum 50 sayfa = 2000 sonuç)
        while collected_for_category < 50 and start_index <= 2000:
            url = f"https://www.googleapis.com/books/v1/volumes?q={category}&langRestrict=tr&maxResults=40&startIndex={start_index}"
            if GOOGLE_API_KEY:
                url += f"&key={GOOGLE_API_KEY}"
            
            try:
                for attempt in range(3):
                    response = requests.get(url)
                    if response.status_code == 200:
                        break
                    print(f"API Yanıtı: {response.status_code}, 3 saniye bekleniyor...")
                    time.sleep(3)
                    
                response.raise_for_status()
                data = response.json()
                
                items = data.get("items", [])
                if not items:
                    break # Bu sayfada hiç kitap yoksa diğer sayfalara bakmayı bırak
                
                for item in items:
                    if collected_for_category >= 50:
                        break
                        
                    volume_info = item.get("volumeInfo", {})
                    
                    description = volume_info.get("description", "")
                    if not description or len(description) < 50:
                        continue
                        
                    # Sadece Türkçe kitapları almak için harf kontrolü
                    tr_chars = set("ğüşıöçĞÜŞİÖÇ")
                    if not any(char in description for char in tr_chars):
                        continue
                    
                    identifiers = volume_info.get("industryIdentifiers", [])
                    isbn = None
                    for idx in identifiers:
                        if idx.get("type") in ["ISBN_13", "ISBN_10"]:
                            isbn = idx.get("identifier")
                            break
                    
                    title = volume_info.get("title", "Bilinmeyen Başlık")
                    authors = volume_info.get("authors", ["Bilinmeyen Yazar"])
                    author = ", ".join(authors)
                    
                    image_links = volume_info.get("imageLinks", {})
                    cover_url = image_links.get("thumbnail", "")
                    
                    book_id = f"book_{book_counter:03d}"
                    price = random.randint(89, 299)
                    
                    book_obj = {
                        "id": book_id,
                        "isbn": isbn,
                        "title": title,
                        "author": author,
                        "genre": category,
                        "description": description,
                        "cover_url": cover_url,
                        "price": price,
                        "series_name": None,
                        "series_order": None,
                        "embedding": None
                    }
                    
                    books_data.append(book_obj)
                    book_counter += 1
                    collected_for_category += 1
                    category_counts[category] += 1
                
                start_index += 40 # Sonraki 40 kitaba geç
                time.sleep(1) # API'yi yormamak için sayfalar arası küçük bir bekleme
                
            except Exception as e:
                print(f"Hata oluştu ({category}): {e}")
                break

    output_file = os.path.join("data", "books.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(books_data, f, ensure_ascii=False, indent=2)

    print("\n--- İŞLEM TAMAMLANDI ---")
    print(f"Toplam toplanan kitap sayısı: {len(books_data)}")
    print("Kategori Dağılımı:")
    for cat, count in category_counts.items():
        print(f"- {cat}: {count} kitap")

if __name__ == "__main__":
    fetch_books()
