import json
import os

def clean_books():
    input_path = os.path.join('data', 'books.json')
    output_path = os.path.join('data', 'books_cleaned.json')
    
    if not os.path.exists(input_path):
        print(f"Hata: {input_path} bulunamadı.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        books = json.load(f)

    print(f"Toplam kitap sayısı (ham): {len(books)}")

    # Temizlik kuralları:
    # 1. Aynı İsim + Aynı Yazar = Tek kitap (Mükerrerleri kaldır)
    # 2. Açıklaması olmayan veya çok kısa olanları (noise) temizle
    # 3. Aynı kitabın farklı türleri varsa, türleri birleştir
    
    unique_books = {}
    removed_empty_desc = 0

    for book in books:
        title = str(book.get('title', '')).strip()
        author = str(book.get('author', '')).strip()
        description = str(book.get('description', '')).strip()
        genre = str(book.get('genre', '')).strip()

        # Kural 2: Açıklama çok kısaysa (örn 20 karakter altı) veya boşsa atla
        if not description or len(description) < 20:
            removed_empty_desc += 1
            continue

        # Kural 1: Benzersiz anahtar oluştur (Başlık + Yazar)
        # Küçük harfe çevirerek daha sağlam eşleşme sağla
        key = f"{title.lower()}|{author.lower()}"

        if key in unique_books:
            # Eğer kitap zaten varsa, türü farklıysa ekle (virgülle ayırarak)
            existing_genre = unique_books[key].get('genre', '')
            if genre and genre not in existing_genre:
                unique_books[key]['genre'] = f"{existing_genre}, {genre}"
        else:
            # Yeni kitap
            unique_books[key] = book

    cleaned_list = []
    for i, book in enumerate(unique_books.values(), 1):
        # Yeni ve sıralı ID ver (örn: book_001)
        book['id'] = f"book_{i:03d}"
        cleaned_list.append(book)
    
    print(f"Boş/Kısa açıklama nedeniyle silinen: {removed_empty_desc}")
    print(f"Mükerrer (tekrar eden) kayıtlar birleştirildi ve ID'ler yeniden sıralandı.")
    print(f"Temizlenmiş kitap sayısı: {len(cleaned_list)}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_list, f, ensure_ascii=False, indent=2)
    
    print(f"Temizlenmiş veri {output_path} dosyasına kaydedildi.")

if __name__ == "__main__":
    clean_books()
