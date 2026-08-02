"""Kural tabanlı günlük plan üretimi (sirkadiyen ritim yaklaşımı).

`gerekce_uret` parametresi bilinçli olarak enjekte edilebilir bırakıldı, ama
`plan_olustur`'un kendisi hep kural tabanlı `_varsayilan_gerekce_uret`'i kullanır —
bunu bilerek değiştirmiyoruz. Gemini tabanlı gerekçe zenginleştirmesi
(`core.services.ai_advisor.gerekceleri_zenginlestir`) burada per-task bir
`gerekce_uret` olarak değil, `ui/app.py`'nin `plan_olustur` başarıyla döndükten
SONRA çağırdığı ayrı bir toplu (batched) adım olarak uygulanıyor — çünkü tüm
görevlerin gerekçesini tek bir LLM çağrısında üretmek, görev başına ayrı çağrı
yapmaktan çok daha hızlı/ucuz. Bu asimetriyi "tutarsızlık" sanıp per-task hale
getirmeye çalışma; bkz. ai_advisor.py'nin modül docstring'i.

`ai_sira` (opsiyonel, varsayılan `None`) Gemini'nin `_sirali_gorevler_uret`'teki
GRUP 2'yi (bugüne ait, sabit saatsiz, esnek teslimli görevler) yeniden sıralama
önerisidir — `core.services.ai_advisor.siralama_onerisi_uret`'ten gelir. Grup 0
(sabit saatli rutinler), grup 1 (kesin teslimli görevler) ve grup 3 (havuzdan
görevler) `ai_sira`'dan HİÇBİR ZAMAN etkilenmez; bunların yerleşimi her zaman
deterministik kalır (sert kısıtlar: uyku, sabit randevu, kesin teslim, kapasite —
LLM'e asla devredilmez). `ai_sira` geçersiz/eksik id kümesi içerirse veya
üretimi başarısız olursa `ai_advisor` zaten `None` döner; bu durumda
`_sirali_gorevler_uret` grup 2 için de kural tabanlı (strateji/enerji bazlı)
sıralamaya döner. `tavsiye_uret` (opsiyonel, varsayılan `_genel_tavsiye_uret`)
aynı "aynı imzada yerine geçebilir" deseniyle `ai_advisor.genel_tavsiye_uret`'e
bağlanabilir.
"""

import logging
from datetime import date, time
from typing import Callable

from core.database import SessionLocal
from core.models import PlanKaydi, Task

logger = logging.getLogger(__name__)

GUN_BASLANGIC = time(6, 0)
GUN_BITIS = time(23, 0)
OGLEDEN_SONRA_BITIS = time(18, 0)

ERTELEME_ONERI_ESIGI = 3
BUYUK_GOREV_ESIGI_DK = 90
YOGUNLASMA_ESIK_DK = 180  # bu süreyi aşan tek bir sürekli boşluk "yoğunlaşma" sayılır


def _dk(t: time) -> int:
    return t.hour * 60 + t.minute


def _saat_str(dk: int) -> str:
    dk %= 24 * 60
    return f"{dk // 60:02d}:{dk % 60:02d}"


def _araligi_cikar(bos: list[tuple[int, int]], cikarilacak: tuple[int, int]) -> list[tuple[int, int]]:
    """`bos` aralık listesinden `cikarilacak` aralığını keser."""
    c_baslangic, c_bitis = cikarilacak
    sonuc = []
    for b_baslangic, b_bitis in bos:
        if c_bitis <= b_baslangic or c_baslangic >= b_bitis:
            sonuc.append((b_baslangic, b_bitis))
            continue
        if c_baslangic > b_baslangic:
            sonuc.append((b_baslangic, c_baslangic))
        if c_bitis < b_bitis:
            sonuc.append((c_bitis, b_bitis))
    return sonuc


def _sarmali_araligi_gune_ekle(bloklar: list[tuple[int, int]], baslangic: time, bitis: time) -> None:
    """Gece yarısını saran (örn. 23:00-07:00) bir aralığı gün sınırları içine kırpıp ekler."""
    gun_baslangic, gun_bitis = _dk(GUN_BASLANGIC), _dk(GUN_BITIS)
    b, e = _dk(baslangic), _dk(bitis)
    if b == e:
        return
    if b < e:
        parcalar = [(b, e)]
    else:
        parcalar = [(b, 24 * 60), (0, e)]
    for p_baslangic, p_bitis in parcalar:
        kirpilmis_baslangic = max(p_baslangic, gun_baslangic)
        kirpilmis_bitis = min(p_bitis, gun_bitis)
        if kirpilmis_baslangic < kirpilmis_bitis:
            bloklar.append((kirpilmis_baslangic, kirpilmis_bitis))


def _bos_araliklar(profil, uygun_olmayan_bloklar: list[dict]) -> list[tuple[int, int]]:
    """Gün sınırları içinde, meşgul bloklar ve uyku penceresi çıkarılmış boş aralıklar."""
    bos = [(_dk(GUN_BASLANGIC), _dk(GUN_BITIS))]

    mesgul: list[tuple[int, int]] = []
    _sarmali_araligi_gune_ekle(mesgul, profil.uyku_baslangic, profil.uyku_bitis)
    for blok in uygun_olmayan_bloklar:
        _sarmali_araligi_gune_ekle(mesgul, blok["start"], blok["end"])

    for aralik in mesgul:
        bos = _araligi_cikar(bos, aralik)
    return sorted(bos)


def _yerlestir(bos: list[tuple[int, int]], sure: int, tercih: tuple[int, int]) -> tuple[int, list[tuple[int, int]]] | None:
    """Süreyi önce tercih edilen pencerede, olmazsa ilk uyan boş aralıkta yerleştirir."""
    t_baslangic, t_bitis = tercih
    for b_baslangic, b_bitis in bos:
        aday_baslangic = max(b_baslangic, t_baslangic)
        aday_bitis = min(b_bitis, t_bitis)
        if aday_bitis - aday_baslangic >= sure:
            yeni_bos = _araligi_cikar(bos, (aday_baslangic, aday_baslangic + sure))
            return aday_baslangic, sorted(yeni_bos)

    for b_baslangic, b_bitis in bos:
        if b_bitis - b_baslangic >= sure:
            yeni_bos = _araligi_cikar(bos, (b_baslangic, b_baslangic + sure))
            return b_baslangic, sorted(yeni_bos)

    return None


def _sabit_saatte_yerlestir(
    bos: list[tuple[int, int]], sure: int, sabit_dk: int
) -> tuple[int, list[tuple[int, int]]] | None:
    """Süreyi tam `sabit_dk`'dan başlatarak yerleştirmeyi dener; slot boşta değilse None döner
    (çağıran, normal önceliğe dayalı yerleştirmeye düşer)."""
    aralik = (sabit_dk, sabit_dk + sure)
    for b_baslangic, b_bitis in bos:
        if b_baslangic <= aralik[0] and aralik[1] <= b_bitis:
            yeni_bos = _araligi_cikar(bos, aralik)
            return sabit_dk, sorted(yeni_bos)
    return None


STRATEJILER = ("oncelik_agirlikli", "sabah_yogun", "dengeli_dagitim")
STRATEJI_ETIKETLERI = {
    "oncelik_agirlikli": "⚖️ Öncelik Ağırlıklı",
    "sabah_yogun": "🌅 Sabah Yoğun",
    "dengeli_dagitim": "🔄 Dengeli Dağıtım",
}
STRATEJI_ACIKLAMALARI = {
    "oncelik_agirlikli": "Görevleri önem sırasına göre yerleştirir: kritik işler en verimli saatlerine, orta öncelikliler öğleden sonraya, düşük öncelikliler günün sonuna gider.",
    "sabah_yogun": "Görevleri mümkün olduğunca en verimli saat aralığına sığdırır; uzun görevler önce yerleşir.",
    "dengeli_dagitim": "Önceliğe bakmaksızın görevleri günün tamamına yayar — tek bir bölgede yoğunlaşma yerine daha dengeli bir dağılım hedefler.",
}


def _tercih_penceresi(oncelik: int, profil, strateji: str = "oncelik_agirlikli") -> tuple[int, int]:
    if strateji == "sabah_yogun":
        return _dk(profil.verimli_baslangic), _dk(profil.verimli_bitis)
    if strateji == "dengeli_dagitim":
        return _dk(GUN_BASLANGIC), _dk(GUN_BITIS)
    if oncelik == 3:
        return _dk(profil.verimli_baslangic), _dk(profil.verimli_bitis)
    if oncelik == 2:
        return _dk(profil.verimli_bitis), _dk(OGLEDEN_SONRA_BITIS)
    return _dk(OGLEDEN_SONRA_BITIS), _dk(GUN_BITIS)


def _varsayilan_gerekce_uret(task: Task, baslangic_dk: int, tercih_penceresinde: bool, profil) -> str:
    if task.sabit_saat is not None:
        if baslangic_dk == _dk(task.sabit_saat):
            return f"Bu rutin görev için ayırdığın saat — {task.sabit_saat:%H:%M}."
        return "Rutin saatinde başka bir şey vardı, en uygun boşluğa alındı."
    if task.teslim_tipi == "kesin":
        return "Bu görevin kesin bir teslim tarihi var, bu yüzden diğer görevlerden önce yerleştirildi."
    if task.due_date is None:
        return "Bu görev havuzdan geldi, boş kalan zamana otomatik yerleştirdim."
    if task.priority == 3:
        if tercih_penceresinde:
            return "Sabah saatleri en verimli zamanın. Kritik görevi buraya yerleştirdim."
        return "En verimli pencerende yeterli boşluk yoktu, kritik görevi en uygun boş zamana yerleştirdim."
    if task.priority == 2:
        return "Öğle sonrası hafif-orta görevler daha uygun. Odak biraz azalıyor."
    return "Düşük zorluk görevi güne son. Hızlı kazanç sağlar."


def _genel_tavsiye_uret(kritik_tercih_penceresinde: int, toplam_kritik: int, enerji_seviyesi: str | None = None) -> str:
    if toplam_kritik == 0:
        tavsiye = (
            "Bugün için kritik öncelikli görev yok. Yine de sabah saatlerini görece "
            "zor işler için ayırman verimliliğini artırabilir."
        )
    else:
        oran = kritik_tercih_penceresinde / toplam_kritik
        if oran == 1:
            yuzde = 35
            tavsiye = (
                "Geçmiş verine göre en verimli olduğun saatler günün en üretken zamanı. "
                "Kritik görevlerin tamamını buraya yerleştirdim. "
                f"**Sabah rutinine sadık kalırsan verimliliğin %{yuzde} artacak.**"
            )
        else:
            yuzde = 15
            tavsiye = (
                "Kritik görevlerin bir kısmı en verimli pencerene sığmadı. "
                f"**Uygun olmayan saatleri azaltırsan verimliliğin %{yuzde} artabilir.**"
            )

    if enerji_seviyesi == "dusuk":
        tavsiye += " Bugünkü düşük enerji seviyene göre hafif işleri öne aldım."
    elif enerji_seviyesi == "yuksek":
        tavsiye += " Bugün enerjin yüksek olduğu için önemli ve uzun işleri öne aldım."
    return tavsiye


def kapasite_kontrolu(gorevler: list[Task], uygun_olmayan_bloklar: list[dict], profil) -> dict:
    """Görevlerin toplam süresini günün müsait zamanıyla karşılaştırır.

    plan_olustur ile aynı _bos_araliklar hesabını kullanır, böylece burada
    "sığar" denen bir gün, plan_olustur çalıştığında da gerçekten sığar.
    """
    bos = _bos_araliklar(profil, uygun_olmayan_bloklar)
    musait_dakika = sum(b - a for a, b in bos)
    toplam_gorev_dakika = sum(t.duration_minutes for t in gorevler)
    fark_dakika = toplam_gorev_dakika - musait_dakika

    return {
        "toplam_gorev_dakika": toplam_gorev_dakika,
        "musait_dakika": musait_dakika,
        "asiri_yuklenme": fark_dakika > 0,
        "fark_dakika": max(fark_dakika, 0),
    }


def _saat_str_to_dk(s: str) -> int:
    saat, dakika = s.split(":")
    return int(saat) * 60 + int(dakika)


def _varsayilan_yogunlasma_tavsiyesi_uret(bosluk: dict) -> str:
    saat, dakika = divmod(bosluk["sure_dakika"], 60)
    return (
        f"Planında {bosluk['baslangic']}-{bosluk['bitis']} arası {saat} saat {dakika} "
        "dakikalık büyük bir boşluk var. Bu bölgeye uygun bir görev eklemeyi veya "
        "görevleri güne daha eşit yaymak için 'Dengeli Dağıtım' stratejisini "
        "denemeyi düşünebilirsin."
    )


def bosluk_analizi_yap(
    kayit: PlanKaydi, profil, uygun_olmayan_bloklar: list[dict] | None = None,
) -> dict | None:
    """Kaydedilmiş bir plandaki görevler arasında (uyku ve uygun olmayan bloklar
    hariç) en büyük sürekli boşluğu bulur. En az 2 görev yoksa (tek görevde
    "yoğunlaşma" kavramı anlamsız) veya en büyük boşluk eşik altındaysa None döner.

    `uygun_olmayan_bloklar` verilmezse yalnızca uyku hariç tutulur — bu durumda
    gerçek bir kısıt (ders/randevu) yüzünden oluşan boşluklar yanlışlıkla
    "yoğunlaşma" sayılabilir, bu yüzden mümkünse çağıran tarafından geçirilmeli
    (bkz. ui/app.py'nin "Plan Oluştur" sekmesindeki kullanımı).
    """
    if len(kayit.dilimler) < 2:
        return None
    bos = _bos_araliklar(profil, uygun_olmayan_bloklar or [])
    for d in kayit.dilimler:
        bos = _araligi_cikar(bos, (_saat_str_to_dk(d["start"]), _saat_str_to_dk(d["end"])))
    if not bos:
        return None
    en_buyuk = max(bos, key=lambda ab: ab[1] - ab[0])
    sure = en_buyuk[1] - en_buyuk[0]
    if sure < YOGUNLASMA_ESIK_DK:
        return None
    return {
        "baslangic": _saat_str(en_buyuk[0]),
        "bitis": _saat_str(en_buyuk[1]),
        "sure_dakika": sure,
    }


def _sirali_gorevler_uret(
    gorevler: list[Task],
    enerji_seviyesi: str | None,
    strateji: str = "oncelik_agirlikli",
    ai_sira: dict[int, int] | None = None,
) -> list[Task]:
    """Sabit saatli (rutin) görevler en spesifik kısıta sahip olduğu için önce, ardından
    kesin teslimliler yerleştirilir — bu sıra stratejiden VE `ai_sira`'dan etkilenmez.
    Ardından bugüne ait esnek görevler; en son da havuzdaki (son tarihi olmayan) görevler
    — bu grup yalnızca diğer tüm görevler yerleştirildikten sonra kalan boşluğa denenir,
    stratejiden bağımsız sabit `(-priority, duration_minutes)` sırasıyla. Bugüne ait esnek
    görevler arasında:
    - `ai_sira` verilmişse (Gemini'nin önerdiği sıralama, bkz. `ai_advisor.siralama_onerisi_uret`)
      ve görevin id'si içindeyse, o sıra kullanılır — bu, tek karar yetkisi Gemini'ye
      bırakılan noktadır; sabit saatli/kesin teslimli/havuzdan görevler bundan asla
      etkilenmez (üsttekiler her zaman kural tabanlı/deterministik kalır).
    - `ai_sira` yoksa veya görev onun içinde değilse, strateji bazlı kural tabanlı sıra:
      - "sabah_yogun": süre azalan sırada (en uzun görev önce, en verimli pencereyi ilk alır).
      - "dengeli_dagitim": oluşturulma sırasında (id), özel bir önceliklendirme yok.
      - "oncelik_agirlikli" (varsayılan): enerji seviyesi "dusuk"/"yuksek" ise "zorluk
        skoru" (öncelik * süre) bazlı sıralanır — düşük enerjide kolay, yüksek enerjide
        zor görevler önce; enerji "orta"/None ise mevcut öncelik bazlı sıralama korunur.
    """
    def anahtar(t: Task) -> tuple:
        if t.sabit_saat is not None:
            grup = 0
        elif t.teslim_tipi == "kesin":
            grup = 1
        elif t.due_date is not None:
            grup = 2
        else:
            grup = 3  # havuzdan — yalnızca boş kalan kapasiteye, stratejiden bağımsız doldurulur
        if grup != 2:
            return (grup, -t.priority, t.duration_minutes)
        if ai_sira is not None and t.id in ai_sira:
            return (grup, ai_sira[t.id], 0)
        if strateji == "sabah_yogun":
            return (grup, -t.duration_minutes, 0)
        if strateji == "dengeli_dagitim":
            return (grup, t.id, 0)
        if enerji_seviyesi in ("dusuk", "yuksek"):
            zorluk = t.priority * t.duration_minutes
            return (grup, zorluk if enerji_seviyesi == "dusuk" else -zorluk, 0)
        return (grup, -t.priority, t.duration_minutes)

    return sorted(gorevler, key=anahtar)


def _plan_hesapla(
    gorevler: list[Task],
    uygun_olmayan_bloklar: list[dict],
    profil,
    gerekce_uret: Callable,
    enerji_seviyesi: str | None,
    strateji: str,
    ai_sira: dict[int, int] | None = None,
    tavsiye_uret: Callable = _genel_tavsiye_uret,
) -> dict:
    """`plan_olustur`'un DB'ye kaydetmeyen saf hesaplama kısmı — alternatif planları
    önizlemek için tekrar tekrar (kaydetmeden) çağrılabilir."""
    bos = _bos_araliklar(profil, uygun_olmayan_bloklar)
    toplam_bos_baslangic = sum(b - a for a, b in bos)

    sirali_gorevler = _sirali_gorevler_uret(gorevler, enerji_seviyesi, strateji, ai_sira)

    dilimler = []
    kritik_tercih_penceresinde = 0
    toplam_kritik = sum(1 for t in sirali_gorevler if t.priority == 3)

    for task in sirali_gorevler:
        sonuc = None
        if task.sabit_saat is not None:
            sonuc = _sabit_saatte_yerlestir(bos, task.duration_minutes, _dk(task.sabit_saat))
        tercih = _tercih_penceresi(task.priority, profil, strateji)
        if sonuc is None:
            sonuc = _yerlestir(bos, task.duration_minutes, tercih)
        if sonuc is None:
            continue
        baslangic_dk, bos = sonuc
        bitis_dk = baslangic_dk + task.duration_minutes
        if profil.buffer_dakika:
            bos = _araligi_cikar(bos, (bitis_dk, bitis_dk + profil.buffer_dakika))
        tercih_penceresinde = tercih[0] <= baslangic_dk and bitis_dk <= tercih[1]
        if task.priority == 3 and tercih_penceresinde:
            kritik_tercih_penceresinde += 1

        gerekce = gerekce_uret(task, baslangic_dk, tercih_penceresinde, profil)
        dilimler.append({
            "task_id": task.id,
            "title": task.title,
            "start": _saat_str(baslangic_dk),
            "end": _saat_str(bitis_dk),
            "duration_minutes": task.duration_minutes,
            "gerekce": gerekce,
            "havuzdan": task.due_date is None,
        })

    dilimler.sort(key=lambda d: d["start"])

    toplam_is_dakika = sum(d["duration_minutes"] for d in dilimler)
    bos_zaman_dakika = toplam_bos_baslangic - toplam_is_dakika
    genel_tavsiye = tavsiye_uret(kritik_tercih_penceresinde, toplam_kritik, enerji_seviyesi)

    return {
        "dilimler": dilimler,
        "toplam_is_dakika": toplam_is_dakika,
        "bos_zaman_dakika": bos_zaman_dakika,
        "genel_tavsiye": genel_tavsiye,
        "yerlesemeyen": len(sirali_gorevler) - len(dilimler),
    }


def plan_olustur(
    user_id: int,
    gun: date,
    gorevler: list[Task],
    uygun_olmayan_bloklar: list[dict],
    profil,
    gerekce_uret: Callable = _varsayilan_gerekce_uret,
    enerji_seviyesi: str | None = None,
    strateji: str = "oncelik_agirlikli",
    ai_sira: dict[int, int] | None = None,
    tavsiye_uret: Callable = _genel_tavsiye_uret,
) -> PlanKaydi:
    """Verilen gün için kural tabanlı bir plan üretir, yeni bir PlanKaydi olarak kaydeder.

    Plana havuzdan (son tarihi olmayan görevlerden) yerleşen olursa, o görevler bu günün
    gerçek görevi haline gelir — `due_date` `gun` olarak güncellenir ve havuzdan çıkar.

    `ai_sira` verilmezse (varsayılan `None`) sıralama %100 kural tabanlıdır — bu parametre
    yalnızca `ui/app.py`'nin `ai_advisor.siralama_onerisi_uret`'ten aldığı sonucu iletmesi
    için var, çağıran belirtmezse davranış hiç değişmez.
    """
    hesap = _plan_hesapla(
        gorevler, uygun_olmayan_bloklar, profil, gerekce_uret, enerji_seviyesi, strateji,
        ai_sira, tavsiye_uret,
    )
    havuzdan_yerlesen_idler = [d["task_id"] for d in hesap["dilimler"] if d["havuzdan"]]

    with SessionLocal() as session:
        if havuzdan_yerlesen_idler:
            session.query(Task).filter(Task.id.in_(havuzdan_yerlesen_idler)).update(
                {"due_date": gun}, synchronize_session=False
            )
        kayit = PlanKaydi(
            user_id=user_id,
            gun=gun,
            dilimler=hesap["dilimler"],
            toplam_is_dakika=hesap["toplam_is_dakika"],
            bos_zaman_dakika=hesap["bos_zaman_dakika"],
            genel_tavsiye=hesap["genel_tavsiye"],
            enerji_seviyesi=enerji_seviyesi,
            strateji=strateji,
        )
        session.add(kayit)
        session.commit()
        session.refresh(kayit)

    logger.info(
        "%s günü için plan oluşturuldu (%s): %d görev yerleştirildi (%d yerleşemedi)",
        gun, strateji, len(hesap["dilimler"]), hesap["yerlesemeyen"],
    )
    return kayit


def alternatif_planlari_uret(
    gorevler: list[Task], uygun_olmayan_bloklar: list[dict], profil, enerji_seviyesi: str | None = None,
) -> dict[str, dict]:
    """Üç sıralama stratejisi için plan önizlemesi üretir — hiçbiri DB'ye kaydedilmez.
    Kullanıcı birini seçince gerçek kayıt `plan_olustur(..., strateji=secilen)` ile yapılır."""
    return {
        strateji: _plan_hesapla(
            gorevler, uygun_olmayan_bloklar, profil, _varsayilan_gerekce_uret, enerji_seviyesi, strateji,
        )
        for strateji in STRATEJILER
    }


def son_plan(user_id: int, gun: date) -> PlanKaydi | None:
    """Kullanıcının o güne ait en son oluşturulan planını döner, yoksa None."""
    with SessionLocal() as session:
        return (
            session.query(PlanKaydi)
            .filter(PlanKaydi.user_id == user_id, PlanKaydi.gun == gun)
            .order_by(PlanKaydi.created_at.desc())
            .first()
        )


def erteleme_onerisi_uret(task: Task, profil=None) -> str:
    """Eşik üzerinde ertelenmiş bir görev için öneri metni üretir (çağıran, eşiği önceden kontrol eder)."""
    if task.duration_minutes > BUYUK_GOREV_ESIGI_DK:
        return (
            f"'{task.title}' {task.postponement_count} kez ertelendi ve {task.duration_minutes} dakika "
            "sürüyor — daha küçük parçalara bölmeyi dene."
        )
    if profil is not None:
        return (
            f"'{task.title}' {task.postponement_count} kez ertelendi — "
            f"{profil.verimli_baslangic:%H:%M} gibi daha uygun bir saate almayı dene."
        )
    return f"'{task.title}' {task.postponement_count} kez ertelendi — farklı bir gün/saat denemeyi düşün."


def erteleme_onerilerini_uret(
    gorevler: list[Task], profil=None, oneri_uret: Callable = erteleme_onerisi_uret,
) -> list[str]:
    """Listedeki eşik üzerinde ertelenmiş her görev için öneri metinlerini döner."""
    return [
        oneri_uret(t, profil) for t in gorevler if t.postponement_count >= ERTELEME_ONERI_ESIGI
    ]


def kullanicinin_planlari(user_id: int) -> list[PlanKaydi]:
    """Kullanıcının tüm plan geçmişini (en yeni gün önce) döner — admin paneli için."""
    with SessionLocal() as session:
        return list(
            session.query(PlanKaydi)
            .filter(PlanKaydi.user_id == user_id)
            .order_by(PlanKaydi.gun.desc(), PlanKaydi.created_at.desc())
        )
