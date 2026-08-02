# Proje: FlowDay

## Ne işe yarar
- Çoklu kullanıcılı (hesap oluşturma/giriş, admin paneli), yerel çalışan günlük görev ve plan yöneticisi.
- Görev CRUD (öncelik: Kritik/Orta/Düşük, süre, son tarih, konum, link, teslim tipi: esnek/kesin).
- Google Takvim ile senkron (push yönü UI'ya bağlı; pull yönü `sync_service.sync_from_google()` kodda var ama hiçbir arayüze bağlı değil; tüm kullanıcılar tek paylaşılan Google hesabını kullanır).
- Kural tabanlı günlük plan üretimi: rutinler + günlük enerji/ruh hali seviyesi + kullanıcının verimli saatlerine göre görevleri yerleştirir, her yerleştirme için gerekçe metni üretir; 3 farklı sıralama stratejisiyle (öncelik ağırlıklı/sabah yoğun/dengeli dağıtım) alternatif plan karşılaştırması sunar. `GEMINI_API_KEY` tanımlıysa kaydedilen plan gerçek bir Gemini çağrısıyla zenginleştirilir (bkz. `core/services/ai_advisor.py`), tanımsızsa otomatik olarak kural tabanlı metne düşer. Gemini ayrıca **bugüne ait esnek görevlerin çalışma sırasına gerçekten karar verir** (sabit saatli rutinler, kesin teslimli görevler ve kapasite/uyku kısıtları her zaman deterministik kalır — bkz. Kurallar).
- Haftalık verimlilik/erteleme raporu, en verimli saat dilimine göre profil güncelleme önerisi, aşırı yüklenme uyarısı, geçmişten kalan görevleri seçili güne taşıma.
- Rutinler (tekrarlayan görevler) ve haftalık tekrar eden sabit/serbest zaman blokları.
- Görev Havuzu: son tarihi olmayan görevler havuzda bekler; plan oluşturulurken boş kalan kapasiteye havuzdan uygun görevler otomatik doldurulur, yerleşince `due_date` o güne güncellenip görev havuzdan çıkar.
- Yoğunlaşma tespiti: plan oluşturulduğunda, görevler arasında (uyku/uygun olmayan bloklar hariç) 3 saati aşan sürekli bir boşluk varsa (`planning_service.bosluk_analizi_yap`) Plan Oluştur sekmesinde bir uyarı + Gemini tavsiyesi + tek tıkla uygulanabilir "Dengeli Dağıtım" alternatifi gösterilir.
- Gün Sonu AI Değerlendirmesi: günün planına göre kaç görev tamamlandı/tamamlanmadı hesaplanıp bir yorum üretilir (AI Planı sekmesinde sadece bugün/geçmiş günler için gösterilir) — `GEMINI_API_KEY` tanımlıysa Gemini, değilse kural tabanlı.
- Veri dışa aktarma (kullanıcı başına tek JSON dosyası), dosya tabanlı loglama.
- Plan gerekçeleri, haftalık rapor analiz metni ve gün sonu yorumu artık Gemini (`google-genai`) ile zenginleştiriliyor — `GEMINI_API_KEY` tanımlı değilse otomatik olarak kural tabanlı metne düşer (bkz. `core/services/ai_advisor.py`).

## Mimari
- `core/models.py` — SQLAlchemy 2.0 ORM: `User` (çoklu kullanıcı, `is_admin`), `Task` (`tur`="gorev"/"etkinlik" — görev ve Google Takvim etkinlikleri aynı tabloda), `Rutin`, `Profil` (`user_id` ile kullanıcı başına bir profil), `HaftalikBlok`, `PlanKaydi` (plan geçmişi, `dilimler` JSON kolon, `strateji`/`enerji_seviyesi` alanları), `GunlukEnerji`.
- `core/database.py` — engine/`SessionLocal`, `core/config.py`'deki `settings`'i kullanır (mutlak DB yolu).
- `core/config.py` — `pydantic-settings`, `.env`'den okunur (DB yolu, Google OAuth dosya yolları, `GEMINI_API_KEY`/`GEMINI_MODEL`).
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
  - `planning_service.py` — kural tabanlı plan üretimi + kapasite kontrolü + alternatif plan stratejileri + görev havuzundan (son tarihi olmayan görevlerden) boş kapasiteyi doldurma; `ai_sira`/`tavsiye_uret`/`erteleme_onerilerini_uret`'in `oneri_uret`'i — hepsi opsiyonel, varsayılanı %100 kural tabanlı
  - `degerlendirme_service.py` — gün sonu değerlendirmesi: günün planına göre tamamlanma oranı + kural tabanlı yorum
  - `report_service.py` — haftalık rapor hesaplamaları + verimli saat önerisi
  - `ai_advisor.py` — Gemini tabanlı gerçek AI zenginleştirme (gerekçe/analiz metni/yorum/genel tavsiye/erteleme önerisi/yoğunlaşma tavsiyesi) + esnek görev sıralaması (`siralama_onerisi_uret`); her çağrı başarısız olursa ilgili kural tabanlı fonksiyona sessizce düşer
  - `export_service.py` — kullanıcının verisini JSON'a döker
- `api/` — FastAPI, sadece görev CRUD (`api/main.py`, `api/schemas.py`).
- `ui/app.py` — Streamlit, tek dosya, sekmeler: Profil / Plan Oluştur / AI Planı / Rapor / (admin kullanıcılar için) Admin. **API'yi çağırmaz**, `core/services/*`'ı doğrudan kullanır — bilinçli mimari karar: UI ve API, `core/` üzerinde çalışan iki bağımsız simetrik adaptör. `ui/`'a özel kurallar için bkz. `ui/CLAUDE.md`.
- `migrations/` — Alembic; şema değişiklikleri buradan geçer, elle `Base.metadata.create_all` kullanılmaz (test fixture'ları hariç).
- `tests/` — pytest, servis katmanı birim testleri; `conftest.py`'deki `test_db` fixture her testte geçici SQLite + her servisin `SessionLocal`'ını monkeypatch eder.

## Kurallar
- Tüm kod, değişken adları, docstring'ler ve kullanıcıya dönen mesajlar **Türkçe** — İngilizce isimlendirmeye geçme.
- `planning_service.gerekce_uret`, `report_service`'in analiz metni fonksiyonu ve `degerlendirme_service.gun_sonu_degerlendirmesi_uret`'in `yorum_uret` parametresi bilinçli olarak değiştirilebilir/enjekte edilebilir bırakıldı; `core/services/ai_advisor.py` artık bu üçünü (+ `genel_tavsiye_uret`, `erteleme_onerisi_uret`) gerçek Gemini çağrılarıyla dolduruyor. `report_service`/`degerlendirme_service`/`planning_service.erteleme_onerilerini_uret`'in enjekte edilen fonksiyonları için `ai_advisor`'daki karşılıkları **aynı imzada, yerine geçebilir** fonksiyonlar (UI ilgili parametreye `ai_advisor.X`'i geçirir). `planning_service.plan_olustur`'un `gerekce_uret`'i ise hep kural tabanlı `_varsayilan_gerekce_uret`'i kullanır ve **değişmez** — Gemini tabanlı gerekçe zenginleştirmesi (`ai_advisor.gerekceleri_zenginlestir`) bunun yerine `ui/app.py`'nin plan kaydedildikten SONRA çağırdığı ayrı, toplu (batched) bir adımdır (tüm görevlerin gerekçesi tek bir LLM çağrısında üretilir — görev başına ayrı çağrı yapmaktan çok daha ucuz/hızlı). Bu asimetriyi "tutarsızlık" sanıp `plan_olustur`'u per-task hale getirmeye çalışma. Yeni AI işi eklerken bu desenleri koru.
- **Gemini'nin görev sıralamasına gerçek karar yetkisi var, ama sınırlı**: `plan_olustur`'un yeni `ai_sira: dict[int, int] | None` parametresi (`ai_advisor.siralama_onerisi_uret`'ten gelir), `_sirali_gorevler_uret`'te SADECE grup 2'yi (bugüne ait, sabit saatsiz, esnek teslimli görevler) etkiler. Sabit saatli rutinler (grup 0), kesin teslimli görevler (grup 1) ve havuzdan görevler (grup 3) her zaman deterministik/kural tabanlı sıralanır — bunlar asla Gemini'ye devredilmez, çünkü LLM'ler kesin aralık aritmetiğinde güvenilir değil ve bir zamanlama uygulamasında geçersiz plan (çakışma, uyku saatine görev, kapasite aşımı) üretme riski var. `ai_sira` geçersiz/eksik id kümesi döndürürse veya Gemini çağrısı başarısız olursa `None`'a düşülür, hiçbir zaman geçersiz bir sıralama plana sızmaz. Yeni bir "AI karar noktası" eklerken aynı ayrımı koru: sert kısıtlar (zaman/kapasite/çakışma) her zaman kod tarafında doğrulanmalı, LLM yalnızca zaten güvenli olan seçenekler arasında karar vermeli.
- Yeni bir servis/model alanı eklerken izlenecek adımlar için `.claude/skills/flowday-yeni-alan-servis` skill'ine bak.
- Yeni bağımlılık eklemeden önce bana sor.

## Dikkat
- `DATABASE_URL` artık `core/config.py`'den gelen **mutlak yol** — cwd'den bağımsız. Bunu tekrar göreli yapma (eskiden farklı dizinden çalıştırınca çift `planner.db` oluşmasına sebep oluyordu).
- İlk Alembic migration'ı (`08e580350355_baslangic.py`) bir süre boş bir no-op'tu ve sıfır veritabanından kurulumu kırıyordu — düzeltildi, ama migration dosyalarını elle düzenlerken "auto-generated ama içi boş" durumlara dikkat et.
- Giriş artık gerçek çoklu kullanıcı sistemi (`User` tablosu, `user_service.py`, bcrypt) — eski tek-kullanıcılı `.env`/`AUTH_PASSWORD_HASH` deseni tamamen kaldırıldı, kodda hiçbir referansı kalmadı.
- Takvim senkronunun **pull yönü** (`sync_service.sync_from_google()`) kodda var ama hiçbir UI butonuna/API endpoint'ine bağlı değil — henüz kullanılmıyor.
- `credentials.json`/`token.json` yerelde mevcut (gitignore'da) — Google Calendar entegrasyonu gerçekten yapılandırılmış durumda; elle test ederken gerçek bir Google hesabına bağlanabilir, dikkatli ol. Google hesabı tüm kullanıcılar arasında paylaşılan tek hesap (kullanıcı başına OAuth henüz yok).
- README.md'nin başındaki bölümler (Sprint 1 raporu, ekip rolleri, FlowDay ürün vizyonu) tarihsel takım dokümantasyonu — güncel teknik durumu yansıtmaz, silme/üzerine yazma. Güncel teknik durum README'nin sonundaki "Uygulama: FlowDay — Teknik Genel Bakış" bölümünde.
- `GEMINI_API_KEY` .env üzerinden tek, paylaşılan bir anahtar — kullanıcı başına ayrı Gemini anahtarı/kotası yok, tüm kullanıcıların AI çağrıları aynı anahtarı/kotayı paylaşır (Google Takvim'deki paylaşılan hesap deseniyle aynı mantık).

## Nasıl çalışmanı istiyorum
- Mimariyi veya özellik kapsamını etkileyen değişikliklerde önce plan sun, onay almadan koda geçme.
- Kod yazmadan önce ilgili testleri oku; yeni servis/fonksiyon eklerken karşılık gelen test dosyasını da güncelle.
- Streamlit değişikliklerini commit'lemeden önce gerçekten çalıştırıp doğrula (AppTest ya da `streamlit run` ile) — sadece syntax kontrolü yetmez.
- Emin değilsen tahmin etme, sor.
