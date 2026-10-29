FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# GPU gerektirmeyen torch surumu imaj boyutunu ciddi oranda kucultur
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bookmind ./bookmind
COPY scripts ./scripts
COPY data/books_cleaned.json ./data/

# Veritabani ve FAISS indeksi imaj olusturulurken hazirlanir
RUN python scripts/build_index.py

EXPOSE 8000
CMD ["uvicorn", "bookmind.api:app", "--host", "0.0.0.0", "--port", "8000"]
