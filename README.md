# Grup-61
Yapay Zeka ve Teknoloji Akademisi Bootcamp 2026

# **Ekip Üyeleri ve Roller**
- Elif Tilgel (Product Owner)
- Elif Ece Gürbüz (Scrum Master)
- Enis Faruk Tatlıpınar (Developer)
- Rabianur Becit (Developer)
- Amr Acar (Developer)  

# Proje Adı: FlowDay (Daily Routine Generator)

# Proje Kapsamı: Yapay Zeka Destekli Bireysel Zaman Yönetimi ve Optimizasyon Sistemi

FlowDay, modern profesyonellerin karşılaştığı en büyük sorunlardan biri olan "karar yorgunluğunu" (decision fatigue) ortadan kaldırmak ve görevleri optimize ederek zaman yönetimi becerilerini geliştirmek için tasarlanmış, yapay zeka destekli proaktif bir zaman yönetimi ve karar destek sistemidir. Kullanıcı; uyuma saati ve gün içerisinde tamamlaması gereken görevleri sisteme girer. Uygulama, bu bilgileri analiz ederek kullanıcıya dengeli ve kişiselleştirilmiş bir günlük plan sunmayı amaçlar.
Geleneksel takvim uygulamalarından farklı olarak, statik bir planlayıcı değil, kullanıcının biyolojik ritmini ve görev zorluklarını analiz eden akıllı bir asistan olarak konumlandırılmıştır.

# Problem Tanımı
Güncel literatür ve piyasa incelemeleri, kullanıcıların günlük görevlerini planlarken yaşadığı en temel sorunun "yetersiz önceliklendirme" ve "zaman dağılımındaki verimsizlik" olduğunu göstermektedir. Geleneksel planlama araçları, statik birer "yapılacaklar listesi" (to-do list) işlevi görmekte; ancak dinamik bir zaman optimizasyonu sağlamamaktadır. Bu proje, yapay zeka entegrasyonu sayesinde kullanıcı odaklı, pratik ve veriye dayalı bir planlama mekanizması sunarak bu boşluğu doldurmayı hedeflemektedir.

# Çözüm
- Verim Pencereleri (Circadian Rhythm Optimization): Uygulama, kullanıcının günlük enerji döngüsünü (sirkadiyen ritim) analiz ederek, en yüksek odak gerektiren görevleri "Deep Work" bloklarına atar.
- Dinamik Enerji Yönetimi: Proje, görevlerin sadece ne kadar sürdüğünü değil, ne kadar zihinsel efor gerektirdiğini takip eder. Enerji seviyesi düştüğünde, sistem otomatik olarak düşük yoğunluklu görevlere (e-posta yanıtlamak, dosya düzenlemek vb.) geçiş yapılmasını önerir.
- Tahminlemeli Risk Analizi: Basit bir karar destek sistemi olarak, kullanıcının planladığı iş yükünün gerçekçi olup olmadığını yapay zeka yardımıyla analiz eder. Planın sarkma ihtimali yüksekse, kullanıcıya proaktif uyarılar göndererek günün yeniden yapılandırılmasını sağlar.
FlowDay ile amacımız, kullanıcılara sadece "zaman kazandırmak" değil, günün sonunda bitkinlik değil tatmin duygusu sağlayan, sürdürülebilir bir çalışma kültürü oluşturmaktır.

# Hedef Kitle
Projenin hedef kitlesi; zaman kısıtlılığı yaşayan akademik personel ve öğrenciler, beyaz yakalı profesyoneller, freelance çalışma modeline sahip bireyler ve gün içerisinde verimlilik artışı hedefleyen genel kullanıcı grubudur.

# Temel Değer Önerisi:  “Kişiselleştirilmiş günlük plan, daha az stres ve daha verimli bir gün”
FlowDay; geleneksel yöntemlerin aksine, sadece görev kaydı tutmakla kalmayıp, bu görevleri yapay zeka algoritmaları aracılığıyla günün en uygun zaman dilimlerine entegre ederek "optimize edilmiş bir zaman yönetimi deneyimi" sunmaktadır. Bu yaklaşım, kullanıcı üzerinde zihinsel yükün azaltılması ve bireysel verimliliğin artırılması sonucunu doğurmaktadır.

# Rakip Analizi


# SWOT Analizi

**Güçlü Yönler**
- Yapayzeka destekli planlama
- Kullanımı kolay arayüz
- Düşük geliştirme maliyeti

**Zayıf Yönler**
- İlk sürümde sınırlı özellik
-  AI önerileri her kullanıcı için her zaman ideal olmayabilir

**Fırsatlar**
-  AItabanlı uygulamalara olan ilginin artması
-  Öğrenci ve çalışan kullanıcı kitlesinin geniş olması

**Tehditler**
- Büyük teknoloji şirketlerinin benzer özellikler geliştirmesi
- Güçlü rakiplerin pazarda yer alması

# Teknolojiler
- Arayüz: Streamlit (Python)
- AI Motoru: OpenAI API
- Proje Yönetimi: GitHub Projects, Confluence
- Versiyon Kontrol: Git / GitHub

# SPRİNT 1 RAPORU

Sprint 1 kapsamında ürün fikri belirlenmiş, ekip içi rol dağılımları gerçekeştirilmiş, ürünün temel iskeletinin oluşturulmasına ve proje yönetim süreçlerinin düzenlenmesine odaklanılmıştır.

# Backlog Dağıtma Mantığı
Backlog oluşturmak ve dağıtmak için Github Project içerisinde "Kanban" ve "Table" özellikleri kullanılmıştır.
Yapılacak işleri ayırabilmek amacıyla Story (Epic), Task ve Sub-Task etiketleri oluşturulmuştur.
Proje süresinde yapılacak ana iş paketleri (kilometretaşları) story olarak açılmış ve bu ana iş paketlerinin içerisinde yer alacak alt iş paketleri ise task ve/veya sub-task olarak eklenmiştir.
Backlog içerisinde yer alan iş paketlerinin hangi Sprint içerisinde yer alacağını belirleyebilmek amacıyla Sprint1, Sprint2, Sprint3 olmak üzere ayrı etiketler oluşturularak iş maddelerine eklenmiştir.

# Toplantı Planları ve Daily Scrum Notları 
Sprint1 süresince ekip içi iletişim  dijital kanallar üzerinden yürütülmüştür. Toplantılar için Zoom ve/veya Google Meetings aracılığı ile gerçekleştirilmiş olup toplantı notları .... (Confluence?) aracılığıyla tutularak toplantı sonunda ekip içinde paylaşılmıştır. Bu sayede projenin belirlenmesinden teknik implementasyon çalışmalarına kadar olan tüm sürecin adım adım takip edilmesi planlanmaktadır.
Confluence linki:

Sprint1 süreci içerisinde aşağıdaki tarihlerde toplantılar gerçekleştirilmiştir:

- 23 Haziran (Tanışma): Ekip üyeleriyle tanışıldı.
- 25 Haziran (Proje belirleme çalışmaları): Farklı proje fikirleri belirlenerek bu fikirler kapsamlı şekilde tartışıldı. Toplam 7 farklı proje üzerine değerlendirme yapıldı.
- 26 Haziran (Proje seçimi): Proje fikirleri arasından FlowDay projesi seçierek ana fikir ve hedef üzerine beyin fırtınası yapıldı.
- 28 Haziran (Kapsam ve Görev Dağılımı): MVP (Minimum Viable Product) için gereken temel özellikler belirlendi; ekip rolleri proje konusuna istinaden daha detaylı şekilde atandı.
- 29 Haziran (Teknik Araştırma): Streamlit ve OpenAI API entegrasyonu üzerine teknik incelemeler yapılmaya başlandı; dokümantasyon hazırlıkları başlatıldı.
- 2 Temmuz (Prototip Kontrolü): Arayüz tasarımı üzerine fikirler görüşüldü ve benzer çalışmalar incelendi. Projenin "Sprint Board" yapısı kuruldu.
- 3 Temmuz (Yoğun Çalışma - I): Streamlit giriş sayfası kodlandı; veri giriş alanları (input fields) ve kullanıcı akışı tamamlandı.
- 4 Temmuz (Yoğun Çalışma - II): AI entegrasyonu (Prompt Engineering) yapıldı.
- 5 Temmuz (Yoğun Çalışma - III): Sprint1 için README dokümantasyonu tamamlandı, Kanban board üzerindeki tüm Sprint 1 görevleri ve backlog kontrol edilerek iş maddelerinin durumları güncellendi. Sprint1 Review gerçekleştirildi.

# Sprint Board Durum Bilgisi

Sprint1 sonunda Kanban board üzerinde Sprint1 kapsamında yer alan tüm görevler "Done" sütununa taşınmıştır. İlgili Kanban board görseli eklenmiştir.

# Ürün Durumu
Ürünün temel arayüzü ve görev giriş ekranı başarıyla oluşturulmuştur.

