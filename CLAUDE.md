# Proje: FlowDay

## Ne işe yarar
- Çoklu kullanıcılı (hesap oluşturma/giriş, admin paneli), yerel çalışan günlük görev ve plan yöneticisi.
- Görev CRUD (öncelik: Kritik/Orta/Düşük, süre, son tarih, konum, link, teslim tipi: esnek/kesin).
- Google Takvim ile senkron (push yönü UI'ya bağlı; pull yönü `sync_service.sync_from_google()` kodda var ama hiçbir arayüze bağlı değil; tüm kullanıcılar tek paylaşılan Google hesabını kullanır).
- Kural tabanlı (henüz gerçek LLM'siz) günlük plan üretimi: rutinler + günlük enerji/ruh hali seviyesi + kullanıcının verimli saatlerine göre görevleri yerleştirir, her yerleştirme için gerekçe metni üretir; 3 farklı sıralama stratejisiyle (öncelik ağırlıklı/sabah yoğun/dengeli dağıtım) alternatif plan karşılaştırması sunar.
- Haftalık verimlilik/erteleme raporu, en verimli saat dilimine göre profil güncelleme önerisi, aşırı yüklenme uyarısı, geçmişten kalan görevleri seçili güne taşıma.
- Rutinler (tekrarlayan görevler) ve haftalık tekrar eden sabit/serbest zaman blokları.
- Görev Havuzu: son tarihi olmayan görevler havuzda bekler; plan oluşturulurken boş kalan kapasiteye havuzdan uygun görevler otomatik doldurulur, yerleşince `due_date` o güne güncellenip görev havuzdan çıkar.
- Gün Sonu AI Değerlendirmesi: günün planına göre kaç görev tamamlandı/tamamlanmadı hesaplanıp kural tabanlı bir yorum üretilir (AI Planı sekmesinde sadece bugün/geçmiş günler için gösterilir).
- Veri dışa aktarma (kullanıcı başına tek JSON dosyası), dosya tabanlı loglama.
- README'deki gerçek OpenAI/AI entegrasyonu **henüz yok** — bilinçli olarak ertelendi, kural tabanlı metin üretimi bunun yerini tutuyor.

## Mimari
- `core/models.py` — SQLAlchemy 2.0 ORM: `User` (çoklu kullanıcı, `is_admin`), `Task` (`tur`="gorev"/"etkinlik" — görev ve Google Takvim etkinlikleri aynı tabloda), `Rutin`, `Profil` (`user_id` ile kullanıcı başına bir profil), `HaftalikBlok`, `PlanKaydi` (plan geçmişi, `dilimler` JSON kolon, `strateji`/`enerji_seviyesi` alanları), `GunlukEnerji`.
- `core/database.py` — engine/`SessionLocal`, `core/config.py`'deki `settings`'i kullanır (mutlak DB yolu).
- `core/config.py` — `pydantic-settings`, `.env`'den okunur (DB yolu, Google OAuth dosya yolları, `OPENAI_*` henüz kullanılmıyor).
- `core/auth.py` — bcrypt parola hash'leme/doğrulama; `core/services/user_service.py` bunun üzerine kayıt/giriş/admin işlemlerini kurar.
- `core/logging_config.py` — `logs/flowday.log`'a dönen (rotating) dosya handler'ı, dış servis yok.
- `core/services/` — iş mantığı, arayüzden bağımsız, doğrudan test edilir:
  - `user_service.py` — kayıt, giriş, admin (listele/sil/yetkilendir/parola sıfırla)
  - `task_service.py` — görev CRUD, erteleme sayacı, gecikmiş görev listesi
  - `calendar_service.py` — Google Calendar API ham iletişim (OAuth)
  - `sync_service.py` — yerel DB ↔ Google Takvim senkron mantığı
  - `profil_service.py` — kullanıcı ayar profili
  - `rutin_service.py` — tekrarlayan görev şablonu CRUD + haftalık materyalize
  - `haftalik_blok_service.py` — haftalık tekrar eden sabit/serbest zaman blokları
  - `enerji_service.py` — günlük enerji/ruh hali seviyesi
  - `planning_service.py` — kural tabanlı plan üretimi + kapasite kontrolü + alternatif plan stratejileri + görev havuzundan (son tarihi olmayan görevlerden) boş kapasiteyi doldurma
  - `degerlendirme_service.py` — gün sonu değerlendirmesi: günün planına göre tamamlanma oranı + kural tabanlı yorum
  - `report_service.py` — haftalık rapor hesaplamaları + verimli saat önerisi
  - `export_service.py` — kullanıcının verisini JSON'a döker
- `api/` — FastAPI, sadece görev CRUD (`api/main.py`, `api/schemas.py`).
- `ui/app.py` — Streamlit, tek dosya, sekmeler: Profil / Plan Oluştur / AI Planı / Rapor / (admin kullanıcılar için) Admin. **API'yi çağırmaz**, `core/services/*`'ı doğrudan kullanır — bilinçli mimari karar: UI ve API, `core/` üzerinde çalışan iki bağımsız simetrik adaptör. `ui/`'a özel kurallar için bkz. `ui/CLAUDE.md`.
- `migrations/` — Alembic; şema değişiklikleri buradan geçer, elle `Base.metadata.create_all` kullanılmaz (test fixture'ları hariç).
- `tests/` — pytest, servis katmanı birim testleri; `conftest.py`'deki `test_db` fixture her testte geçici SQLite + her servisin `SessionLocal`'ını monkeypatch eder.

## Kurallar
- Tüm kod, değişken adları, docstring'ler ve kullanıcıya dönen mesajlar **Türkçe** — İngilizce isimlendirmeye geçme.
- `planning_service.gerekce_uret`, `report_service`'in analiz metni fonksiyonu ve `degerlendirme_service.gun_sonu_degerlendirmesi_uret`'in `yorum_uret` parametresi bilinçli olarak değiştirilebilir/enjekte edilebilir bırakıldı — ileride gerçek OpenAI entegrasyonu bu tek noktaları değiştirecek, geri kalan mantığa dokunmayacak şekilde tasarlandı. Yeni AI işi eklerken bu deseni koru.
- Yeni bir servis/model alanı eklerken izlenecek adımlar için `.claude/skills/flowday-yeni-alan-servis` skill'ine bak.
- Yeni bağımlılık eklemeden önce bana sor.

## Dikkat
- `DATABASE_URL` artık `core/config.py`'den gelen **mutlak yol** — cwd'den bağımsız. Bunu tekrar göreli yapma (eskiden farklı dizinden çalıştırınca çift `planner.db` oluşmasına sebep oluyordu).
- İlk Alembic migration'ı (`08e580350355_baslangic.py`) bir süre boş bir no-op'tu ve sıfır veritabanından kurulumu kırıyordu — düzeltildi, ama migration dosyalarını elle düzenlerken "auto-generated ama içi boş" durumlara dikkat et.
- Giriş artık gerçek çoklu kullanıcı sistemi (`User` tablosu, `user_service.py`, bcrypt) — eski tek-kullanıcılı `.env`/`AUTH_PASSWORD_HASH` deseni tamamen kaldırıldı, kodda hiçbir referansı kalmadı.
- Takvim senkronunun **pull yönü** (`sync_service.sync_from_google()`) kodda var ama hiçbir UI butonuna/API endpoint'ine bağlı değil — henüz kullanılmıyor.
- `credentials.json`/`token.json` yerelde mevcut (gitignore'da) — Google Calendar entegrasyonu gerçekten yapılandırılmış durumda; elle test ederken gerçek bir Google hesabına bağlanabilir, dikkatli ol. Google hesabı tüm kullanıcılar arasında paylaşılan tek hesap (kullanıcı başına OAuth henüz yok).
- README.md'nin başındaki bölümler (Sprint 1 raporu, ekip rolleri, FlowDay ürün vizyonu) tarihsel takım dokümantasyonu — güncel teknik durumu yansıtmaz, silme/üzerine yazma. Güncel teknik durum README'nin sonundaki "Uygulama: FlowDay — Teknik Genel Bakış" bölümünde.

## Nasıl çalışmanı istiyorum
- Mimariyi veya özellik kapsamını etkileyen değişikliklerde önce plan sun, onay almadan koda geçme.
- Kod yazmadan önce ilgili testleri oku; yeni servis/fonksiyon eklerken karşılık gelen test dosyasını da güncelle.
- Streamlit değişikliklerini commit'lemeden önce gerçekten çalıştırıp doğrula (AppTest ya da `streamlit run` ile) — sadece syntax kontrolü yetmez.
- Emin değilsen tahmin etme, sor.
