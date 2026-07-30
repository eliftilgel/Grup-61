# Proje: FlowDay

## Ne işe yarar
- Tek kullanıcılı, yerel çalışan günlük görev ve plan yöneticisi (README'de "FlowDay" olarak tanıtılan vizyonun MVP'si, ürün adı da "FlowDay").
- Görev CRUD (öncelik: Kritik/Orta/Düşük, süre, son tarih).
- Google Takvim ile senkron (push yönü UI'ya bağlı; pull yönü `sync_service.sync_from_google()` kodda var ama hiçbir arayüze bağlı değil).
- Kural tabanlı (henüz gerçek LLM'siz) günlük plan üretimi: görevleri önceliğe/kullanıcının verimli saatlerine göre yerleştirir, her yerleştirme için gerekçe metni üretir.
- Haftalık verimlilik/erteleme raporu, aşırı yüklenme uyarısı, geçmişten kalan görevleri seçili güne taşıma.
- Veri dışa aktarma (tek JSON dosyası), dosya tabanlı loglama, tek kullanıcılı opsiyonel parola girişi.
- README'deki gerçek OpenAI/AI entegrasyonu **henüz yok** — bilinçli olarak ertelendi, kural tabanlı metin üretimi bunun yerini tutuyor.

## Çalıştırma
- Kurulum: `pip install -r requirements.txt && pip install -e .`
- Migration: `alembic upgrade head`
- UI: `streamlit run ui/app.py` (http://localhost:8501)
- API: `uvicorn api.main:app --reload` (sadece görev CRUD; takvim/plan/rapor endpoint'i yok)
- Test: `pytest`
- Lint: tanımlı değil (ruff/flake8 kurulu değil)

## Mimari
- `core/models.py` — SQLAlchemy 2.0 ORM: `Task`, `CalendarEvent`, `Profil` (id=1 tek satır, gerçek çoklu kullanıcı değil), `PlanKaydi` (plan geçmişi, `dilimler` JSON kolon).
- `core/database.py` — engine/`SessionLocal`, `core/config.py`'deki `settings`'i kullanır (mutlak DB yolu).
- `core/config.py` — `pydantic-settings`, `.env`'den okunur (DB yolu, Google OAuth dosya yolları, `AUTH_PASSWORD_HASH`, `OPENAI_*` henüz kullanılmıyor).
- `core/auth.py` — bcrypt parola doğrulama (tek kullanıcı; `.env`'de hash yoksa giriş ekranı tamamen devre dışı).
- `core/logging_config.py` — `logs/flowday.log`'a dönen (rotating) dosya handler'ı, dış servis yok.
- `core/services/` — iş mantığı, arayüzden bağımsız, doğrudan test edilir:
  - `task_service.py` — görev CRUD, erteleme sayacı, gecikmiş görev listesi
  - `calendar_service.py` — Google Calendar API ham iletişim (OAuth)
  - `sync_service.py` — yerel DB ↔ Google Takvim senkron mantığı
  - `profil_service.py` — kullanıcı ayar profili
  - `planning_service.py` — kural tabanlı plan üretimi + kapasite kontrolü
  - `report_service.py` — haftalık rapor hesaplamaları
  - `export_service.py` — tüm veriyi JSON'a döker
- `api/` — FastAPI, sadece görev CRUD (`api/main.py`, `api/schemas.py`).
- `ui/app.py` — Streamlit, tek dosya, 4 sekme (Profil / Plan Oluştur / AI Planı / Rapor). **API'yi çağırmaz**, `core/services/*`'ı doğrudan kullanır — bilinçli mimari karar: UI ve API, `core/` üzerinde çalışan iki bağımsız simetrik adaptör.
- `migrations/` — Alembic; şema değişiklikleri buradan geçer, elle `Base.metadata.create_all` kullanılmaz (test fixture'ları hariç).
- `tests/` — pytest, servis katmanı birim testleri; `conftest.py`'deki `test_db` fixture her testte geçici SQLite + her servisin `SessionLocal`'ını monkeypatch eder.

## Kurallar
- Tüm kod, değişken adları, docstring'ler ve kullanıcıya dönen mesajlar **Türkçe** — İngilizce isimlendirmeye geçme.
- Yeni bir servis eklerken `tests/conftest.py`'deki `test_db` fixture'ına o servisin `SessionLocal`'ını da eklemeyi unutma — aksi halde testler gerçek `planner.db`'ye yazar.
- `planning_service.gerekce_uret` ve `report_service`'in analiz metni fonksiyonu bilinçli olarak değiştirilebilir/enjekte edilebilir bırakıldı — ileride gerçek OpenAI entegrasyonu bu tek noktaları değiştirecek, geri kalan mantığa dokunmayacak şekilde tasarlandı. Yeni AI işi eklerken bu deseni koru.
- Yeni bir Task/Profil/PlanKaydi alanı eklerken sıra: `core/models.py` → Alembic migration (`alembic revision --autogenerate`, elle doğrula) → ilgili servis → gerekiyorsa `tests/conftest.py`.
- `ui/app.py`'de `st.set_page_config()` dosyanın en başında olmalı (Streamlit kısıtı) — üstüne yeni bir `st.*` çağrısı ekleme.
- Yeni bağımlılık eklemeden önce bana sor.

## Dikkat
- `DATABASE_URL` artık `core/config.py`'den gelen **mutlak yol** — cwd'den bağımsız. Bunu tekrar göreli yapma (eskiden farklı dizinden çalıştırınca çift `planner.db` oluşmasına sebep oluyordu).
- İlk Alembic migration'ı (`08e580350355_baslangic.py`) bir süre boş bir no-op'tu ve sıfır veritabanından kurulumu kırıyordu — düzeltildi, ama migration dosyalarını elle düzenlerken "auto-generated ama içi boş" durumlara dikkat et.
- `AUTH_PASSWORD_HASH` `.env`'de ayarlı değilse giriş ekranı tamamen devre dışı — bu kasıtlı, geriye dönük uyumlu bir varsayılan, "bug" değil.
- Takvim senkronunun **pull yönü** (`sync_service.sync_from_google()`) kodda var ama hiçbir UI butonuna/API endpoint'ine bağlı değil — henüz kullanılmıyor.
- `credentials.json`/`token.json` yerelde mevcut (gitignore'da) — Google Calendar entegrasyonu gerçekten yapılandırılmış durumda; elle test ederken gerçek bir Google hesabına bağlanabilir, dikkatli ol.
- README.md'nin başındaki bölümler (Sprint 1 raporu, ekip rolleri, FlowDay ürün vizyonu) tarihsel takım dokümantasyonu — güncel teknik durumu yansıtmaz, silme/üzerine yazma. Güncel teknik durum README'nin sonundaki "Uygulama: FlowDay — Teknik Genel Bakış" bölümünde.

## Nasıl çalışmanı istiyorum
- Mimariyi veya özellik kapsamını etkileyen değişikliklerde önce plan sun, onay almadan koda geçme.
- Kod yazmadan önce ilgili testleri oku; yeni servis/fonksiyon eklerken karşılık gelen test dosyasını da güncelle.
- Streamlit değişikliklerini commit'lemeden önce gerçekten çalıştırıp doğrula (AppTest ya da `streamlit run` ile) — sadece syntax kontrolü yetmez.
- Emin değilsen tahmin etme, sor.
