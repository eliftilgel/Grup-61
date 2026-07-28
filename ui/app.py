import json
import logging
from datetime import date, datetime, time as dt_time, timedelta

import streamlit as st

from core.auth import sifre_dogrula
from core.config import settings
from core.logging_config import setup_logging
from core.services import export_service, planning_service, profil_service, report_service
from core.services.task_service import (
    complete_task,
    create_task,
    delete_task,
    gecikmis_gorevleri_listele,
    list_tasks,
    update_task,
)

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Planla!", layout="wide")

if settings.auth_password_hash and not st.session_state.get("authenticated"):
    st.markdown(
        "<h2 style='text-align:center; margin-top:80px;'>🔒 Planla!</h2>", unsafe_allow_html=True
    )
    _giris_col1, _giris_col2, _giris_col3 = st.columns([1, 1, 1])
    with _giris_col2:
        with st.form("giris_formu"):
            girilen_sifre = st.text_input("Parola", type="password")
            if st.form_submit_button("Giriş Yap", use_container_width=True):
                if sifre_dogrula(settings.auth_password_hash, girilen_sifre):
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Parola hatalı")
    st.stop()

# ---------------------------------------------------------------------------
# Renkler — dataviz skill'inin durum paletinden (good/warning/critical) +
# kategorik mavi/mor. Orijinal FlowDay mockup'undaki mor-indigo gradyan
# kimliğini yaklaşık olarak uygulayan hafif bir CSS katmanı (piksel-mükemmel
# değil).
# ---------------------------------------------------------------------------
RENK_IYI = "#0ca30c"
RENK_UYARI = "#fab219"
RENK_MAVI = "#2a78d6"
RENK_KRITIK = "#d03b3b"
RENK_MOR = "#4a3aa7"
GRADYAN = f"linear-gradient(135deg, {RENK_MOR} 0%, {RENK_MAVI} 100%)"

ONCELIK_ETIKET = {3: "KRİTİK", 2: "ORTA", 1: "DÜŞÜK"}
ONCELIK_RENK = {3: RENK_KRITIK, 2: RENK_UYARI, 1: RENK_IYI}
ONCELIK_METIN_RENK = {3: "#ffffff", 2: "#0b0b0b", 1: "#ffffff"}

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

_STYLE = """
<style>
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #ffffff;
    padding: 6px;
    border-radius: 14px;
    box-shadow: 0 1px 3px rgba(11,11,11,0.08);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    background: __GRADYAN__ !important;
}
.stTabs [aria-selected="true"] p {
    color: #ffffff !important;
    font-weight: 600;
}
div.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: __GRADYAN__;
    border: none;
}
.fd-header {
    background: __GRADYAN__;
    color: #ffffff;
    padding: 14px 20px;
    border-radius: 14px 14px 0 0;
    font-size: 1.1rem;
    font-weight: 700;
    margin-top: 8px;
}
.fd-card {
    background: #ffffff;
    border-radius: 0 0 14px 14px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(11,11,11,0.08);
    margin-bottom: 24px;
}
.fd-avatar {
    width: 72px; height: 72px; border-radius: 50%;
    background: __GRADYAN__; color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.4rem; font-weight: 700; margin: 0 auto 12px auto;
}
.fd-stat-tile {
    border-radius: 12px; padding: 18px; text-align: center;
    font-weight: 700; margin-bottom: 12px;
}
.fd-stat-tile .deger { font-size: 1.8rem; display: block; }
.fd-stat-tile .etiket { font-size: 0.85rem; font-weight: 500; opacity: 0.9; }
.fd-info-card {
    background: #f9f9f7; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;
}
.fd-badge {
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    background: __RENK_IYI__; color: #fff; font-size: 0.8rem; font-weight: 600;
}
.fd-blok-row, .fd-gorev-row {
    border-left: 4px solid __RENK_MAVI__; background: #f9f9f7;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
}
.fd-rozet {
    display: inline-block; padding: 2px 10px; border-radius: 6px;
    font-size: 0.75rem; font-weight: 700; margin-right: 8px;
}
.fd-dilim-card {
    background: #f9f9f7; border-left: 4px solid __RENK_MOR__;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;
}
.fd-oneri-kutu {
    background: #e6f6f2; border-radius: 10px; padding: 16px 20px; margin-top: 16px;
    border-left: 4px solid __RENK_IYI__;
}
.fd-analiz-kutu {
    background: #e8f0fb; border-radius: 10px; padding: 16px 20px; margin-top: 16px;
    border-left: 4px solid __RENK_MAVI__;
}
.fd-bucket-track {
    background: #e1e0d9; border-radius: 999px; height: 22px;
}
.fd-bucket-fill {
    background: __RENK_MAVI__; border-radius: 999px; height: 22px;
}
</style>
"""
_STYLE = (
    _STYLE.replace("__GRADYAN__", GRADYAN)
    .replace("__RENK_IYI__", RENK_IYI)
    .replace("__RENK_MAVI__", RENK_MAVI)
    .replace("__RENK_MOR__", RENK_MOR)
)
st.markdown(_STYLE, unsafe_allow_html=True)

st.markdown(
    "<h1 style='text-align:center; margin-bottom:0;'>🎯 Planla!</h1>"
    "<p style='text-align:center; color:#898781; margin-top:4px;'>"
    "Dinamik Günlük Planlayıcı</p>",
    unsafe_allow_html=True,
)

with st.expander("📅 Google Takvim'e etkinlik ekle"):
    with st.form("yeni_etkinlik", clear_on_submit=True):
        ev_title = st.text_input("Başlık", key="ev_baslik")
        ev_desc = st.text_area("Açıklama", height=80, key="ev_aciklama")
        col_a, col_b, col_c = st.columns(3)
        ev_gun = col_a.date_input("Tarih", key="ev_gun")
        ev_bas = col_b.time_input("Başlangıç", value=dt_time(9, 0), key="ev_bas")
        ev_bit = col_c.time_input("Bitiş", value=dt_time(10, 0), key="ev_bit")
        if st.form_submit_button("Google Takvim'e ekle"):
            if not ev_title.strip():
                st.error("Başlık boş olamaz")
            elif ev_bit <= ev_bas:
                st.error("Bitiş, başlangıçtan sonra olmalı")
            else:
                from core.services.sync_service import create_event_everywhere

                start_iso = datetime.combine(ev_gun, ev_bas).astimezone().isoformat()
                end_iso = datetime.combine(ev_gun, ev_bit).astimezone().isoformat()
                create_event_everywhere(ev_title, start_iso, end_iso, ev_desc)
                st.success("Etkinlik Google Takvim'e eklendi")
                st.rerun()

tab_profil, tab_plan, tab_ai, tab_rapor = st.tabs(
    ["👤 Profil", "📝 Plan Oluştur", "🗓️ AI Planı", "📊 Rapor"]
)

# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------
with tab_profil:
    st.markdown("<div class='fd-header'>👤 Profil &amp; Ayarlar</div>", unsafe_allow_html=True)
    st.markdown("<div class='fd-card'>", unsafe_allow_html=True)

    profil = profil_service.get_or_create()
    baslangic_harfleri = "".join(p[0].upper() for p in profil.ad_soyad.split()[:2]) or "?"
    st.markdown(
        f"<div class='fd-avatar'>{baslangic_harfleri}</div>"
        f"<p style='text-align:center; font-weight:700; margin-bottom:0;'>{profil.ad_soyad or 'Ad Soyad'}</p>"
        f"<p style='text-align:center; color:#898781; margin-top:0;'>{profil.e_posta or '—'}</p>",
        unsafe_allow_html=True,
    )

    with st.form("profil_form"):
        p_ad = st.text_input("👤 Ad Soyad", value=profil.ad_soyad)
        p_eposta = st.text_input("✉️ E-posta", value=profil.e_posta)
        st.caption("⚡ En Verimli Olduğun Saatler")
        col1, col2 = st.columns(2)
        p_verimli_b = col1.time_input("Başlangıç", value=profil.verimli_baslangic, key="p_verimli_b")
        p_verimli_e = col2.time_input("Bitiş", value=profil.verimli_bitis, key="p_verimli_e")
        st.caption("😴 Varsayılan Uyku Saatleri")
        col3, col4 = st.columns(2)
        p_uyku_b = col3.time_input("Başlangıç", value=profil.uyku_baslangic, key="p_uyku_b")
        p_uyku_e = col4.time_input("Bitiş", value=profil.uyku_bitis, key="p_uyku_e")
        p_hedef = st.number_input("🎯 Günlük Hedef (görev sayısı)", min_value=1, value=profil.gunluk_hedef)

        if st.form_submit_button("💾 Kaydet", type="primary", use_container_width=True):
            try:
                profil_service.save(p_ad, p_eposta, p_verimli_b, p_verimli_e, p_uyku_b, p_uyku_e, p_hedef)
                st.success("Profil kaydedildi")
                st.rerun()
            except ValueError as e:
                logger.warning("Profil kaydetme hatası: %s", e)
                st.error(str(e))

    if st.button("🚪 Çıkış Yap"):
        if settings.auth_password_hash:
            st.session_state["authenticated"] = False
            st.rerun()
        else:
            st.info("Giriş ekranı yapılandırılmadığı için çıkılacak bir oturum yok (.env'de AUTH_PASSWORD_HASH ayarlayın).")

    st.divider()
    st.subheader("🗂️ Veri Yönetimi")
    st.caption("Tüm görevlerini, takvim etkinliklerini, profilini ve plan geçmişini tek bir JSON dosyası olarak indir.")
    yedek = export_service.tum_veriyi_disa_aktar()
    st.download_button(
        "📦 Verilerini İndir (JSON)",
        data=json.dumps(yedek, ensure_ascii=False, indent=2),
        file_name=f"planla_yedek_{date.today():%Y-%m-%d}.json",
        mime="application/json",
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Plan Oluştur
# ---------------------------------------------------------------------------
with tab_plan:
    st.markdown("<div class='fd-header'>📝 Günlük Plan Oluştur</div>", unsafe_allow_html=True)
    st.markdown("<div class='fd-card'>", unsafe_allow_html=True)

    profil = profil_service.get_or_create()
    secili_gun = st.date_input(
        "📅 Günü Seç", value=st.session_state.get("secili_gun", date.today()), key="secili_gun"
    )

    if st.session_state.get("bloklar_gun") != secili_gun:
        st.session_state["uygun_olmayan_bloklar"] = [
            {"start": profil.uyku_baslangic, "end": profil.uyku_bitis, "label": "😴 Uyku Saati"}
        ]
        st.session_state["bloklar_gun"] = secili_gun

    if secili_gun >= date.today():
        gecikmisler = gecikmis_gorevleri_listele(date.today())
        if gecikmisler:
            st.subheader("⏰ Geçmişten Kalan Görevler")
            for gecikmis in gecikmisler:
                gc1, gc2 = st.columns([5, 2])
                gun_farki = (date.today() - gecikmis.due_date).days
                gc1.markdown(
                    f"<div class='fd-gorev-row'>"
                    f"<span class='fd-rozet' style='background:{ONCELIK_RENK[gecikmis.priority]}; "
                    f"color:{ONCELIK_METIN_RENK[gecikmis.priority]};'>{ONCELIK_ETIKET[gecikmis.priority]}</span>"
                    f"<strong>{gecikmis.title}</strong>"
                    f"<br><span style='color:#898781; font-size:0.85rem;'>{gun_farki} gündür gecikmiş</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if gc2.button(
                    f"→ {secili_gun:%d.%m}'e taşı", key=f"tasi_{gecikmis.id}",
                    help="Görevi seçili güne taşı",
                ):
                    update_task(
                        gecikmis.id, gecikmis.title, gecikmis.description, gecikmis.priority,
                        due_date=secili_gun, duration_minutes=gecikmis.duration_minutes,
                    )
                    st.rerun()

    st.subheader("🚫 Uygun Olmayan Saatler (Ders, Uyku vb.)")
    bcol1, bcol2, bcol3, bcol4 = st.columns([2, 2, 3, 1])
    blok_bas = bcol1.time_input("Başlangıç", value=dt_time(9, 0), key="blok_bas")
    blok_bit = bcol2.time_input("Bitiş", value=dt_time(12, 0), key="blok_bit")
    blok_etiket = bcol3.text_input(
        "Etiket", key="blok_etiket", placeholder="ör: Ders"
    )
    if bcol4.button("+ Ekle"):
        if blok_bit > blok_bas:
            st.session_state["uygun_olmayan_bloklar"].append(
                {"start": blok_bas, "end": blok_bit, "label": blok_etiket or "Meşgul"}
            )
            st.rerun()
        else:
            st.error("Bitiş, başlangıçtan sonra olmalı")

    for i, blok in enumerate(st.session_state["uygun_olmayan_bloklar"]):
        c1, c2 = st.columns([5, 1])
        c1.markdown(
            f"<div class='fd-blok-row'>{blok['label']}"
            f"<br><span style='color:#898781; font-size:0.85rem;'>"
            f"{blok['start'].strftime('%H:%M')}–{blok['end'].strftime('%H:%M')}</span></div>",
            unsafe_allow_html=True,
        )
        if c2.button("Kaldır", key=f"kaldir_blok_{i}"):
            st.session_state["uygun_olmayan_bloklar"].pop(i)
            st.rerun()

    st.subheader("📋 Yapılması Gereken İşler")
    g_title = st.text_input("İş adı (ör: Raporu yaz)", key="g_title")
    g_sure = st.number_input("Süre (dakika)", min_value=1, value=30, key="g_sure")
    g_oncelik = st.selectbox(
        "Öncelik Seç", options=[3, 2, 1], format_func=lambda p: ONCELIK_ETIKET[p], key="g_oncelik"
    )
    if st.button("+ Görev Ekle", type="primary", use_container_width=True):
        try:
            create_task(g_title, priority=g_oncelik, due_date=secili_gun, duration_minutes=g_sure)
            st.rerun()
        except ValueError as e:
            logger.warning("Görev oluşturma hatası: %s", e)
            st.error(str(e))

    gunun_gorevleri = list_tasks(due_date=secili_gun)
    if not gunun_gorevleri:
        st.caption("Bu gün için henüz görev eklenmedi.")

    for task in gunun_gorevleri:
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        tamamlandi_isareti = " ✓" if task.done else ""
        c1.markdown(
            f"<div class='fd-gorev-row'>"
            f"<span class='fd-rozet' style='background:{ONCELIK_RENK[task.priority]}; "
            f"color:{ONCELIK_METIN_RENK[task.priority]};'>{ONCELIK_ETIKET[task.priority]}</span>"
            f"<strong>{task.title}{tamamlandi_isareti}</strong>"
            f"<br><span style='color:#898781; font-size:0.85rem;'>⏱ {task.duration_minutes} dakika</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if c2.button("✓", key=f"tamamla_{task.id}", disabled=task.done, help="Görevi tamamla"):
            complete_task(task.id)
            st.rerun()
        if c3.button("✎", key=f"duzenle_{task.id}", help="Görevi düzenle"):
            st.session_state["duzenle_id"] = None if st.session_state.get("duzenle_id") == task.id else task.id
            st.rerun()
        if c4.button("🗑", key=f"sil_{task.id}", help="Görevi sil"):
            delete_task(task.id)
            st.rerun()

        if st.session_state.get("duzenle_id") == task.id:
            with st.form(f"duzenle_form_{task.id}"):
                e_title = st.text_input("Başlık", value=task.title)
                e_sure = st.number_input("Süre (dakika)", min_value=1, value=task.duration_minutes)
                e_oncelik = st.selectbox(
                    "Öncelik", options=[3, 2, 1], index=[3, 2, 1].index(task.priority),
                    format_func=lambda p: ONCELIK_ETIKET[p],
                )
                e_due = st.date_input("Son tarih", value=task.due_date or secili_gun)
                if st.form_submit_button("Kaydet"):
                    try:
                        update_task(task.id, e_title, task.description, e_oncelik, e_due, e_sure)
                        st.session_state["duzenle_id"] = None
                        st.rerun()
                    except ValueError as e:
                        logger.warning("Görev düzenleme hatası: %s", e)
                        st.error(str(e))

    aktif_gorevler = list_tasks(include_done=False, due_date=secili_gun)
    if aktif_gorevler:
        kapasite = planning_service.kapasite_kontrolu(
            aktif_gorevler, st.session_state["uygun_olmayan_bloklar"], profil
        )
        if kapasite["asiri_yuklenme"]:
            st.warning(
                f"⚠️ Bugünkü işlerin toplam {kapasite['toplam_gorev_dakika']} dk, "
                f"müsait zamanın {kapasite['musait_dakika']} dk — "
                f"{kapasite['fark_dakika']} dk sığmayabilir."
            )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 Planı Oluştur", type="primary", use_container_width=True):
        if not aktif_gorevler:
            st.warning("Plan oluşturmak için en az bir görev ekleyin.")
        else:
            planning_service.plan_olustur(
                secili_gun, aktif_gorevler, st.session_state["uygun_olmayan_bloklar"], profil
            )
            st.success("Plan oluşturuldu! 'AI Planı' sekmesinden görüntüleyebilirsin.")

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# AI Planı
# ---------------------------------------------------------------------------
with tab_ai:
    st.markdown(
        "<div class='fd-header'>🗓️ AI Tarafından Oluşturulan Plan</div>", unsafe_allow_html=True
    )
    st.markdown("<div class='fd-card'>", unsafe_allow_html=True)

    gosterilecek_gun = st.session_state.get("secili_gun", date.today())
    kayit = planning_service.son_plan(gosterilecek_gun)

    if kayit is None:
        st.info("Bu gün için henüz bir plan oluşturulmadı — 'Plan Oluştur' sekmesinden oluşturabilirsin.")
    else:
        aktif_gorev_sayisi = len(list_tasks(include_done=False, due_date=kayit.gun))
        yerlesemeyen_sayisi = max(aktif_gorev_sayisi - len(kayit.dilimler), 0)
        rozet = "Tamamen Planlandı ✓" if not yerlesemeyen_sayisi and kayit.dilimler else "Planlanamadı" if not kayit.dilimler else "Kısmen Planlandı"

        gun_adi = GUNLER[kayit.gun.weekday()]
        gun_metni = f"{gun_adi}, {kayit.gun.day} {AYLAR[kayit.gun.month - 1]} {kayit.gun.year}"
        st.markdown(
            f"<div class='fd-info-card'>"
            f"<span style='color:#898781;'>{gun_metni}</span><br>"
            f"<strong style='font-size:1.2rem;'>Günlük Plan Hazır</strong><br>"
            f"<span class='fd-badge'>{rozet}</span></div>",
            unsafe_allow_html=True,
        )
        if yerlesemeyen_sayisi:
            st.warning(f"⚠️ {yerlesemeyen_sayisi} görev bu plana sığmadı — gün dolu.")

        scol1, scol2 = st.columns(2)
        scol1.markdown(
            f"<div class='fd-info-card' style='text-align:center;'>"
            f"<span style='color:#898781;'>Toplam İş Süresi</span><br>"
            f"<strong style='font-size:1.4rem;'>{kayit.toplam_is_dakika // 60}s "
            f"{kayit.toplam_is_dakika % 60}dk</strong></div>",
            unsafe_allow_html=True,
        )
        scol2.markdown(
            f"<div class='fd-info-card' style='text-align:center;'>"
            f"<span style='color:#898781;'>Boş Zaman</span><br>"
            f"<strong style='font-size:1.4rem;'>{kayit.bos_zaman_dakika // 60}s "
            f"{kayit.bos_zaman_dakika % 60}dk</strong></div>",
            unsafe_allow_html=True,
        )

        st.subheader("📊 Önerilen Sıralama")
        if not kayit.dilimler:
            st.caption("Hiçbir görev yerleştirilemedi.")
        for dilim in kayit.dilimler:
            st.markdown(
                f"<div class='fd-dilim-card'>"
                f"<span style='color:#898781; font-size:0.85rem;'>{dilim['start']} — {dilim['end']}</span><br>"
                f"<strong>📝 {dilim['title']} ({dilim['duration_minutes']} dk)</strong><br>"
                f"<span style='color:{RENK_MAVI}; font-style:italic; font-size:0.9rem;'>"
                f"💬 {dilim['gerekce']}</span></div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            f"<div class='fd-oneri-kutu'>💡 <strong>Yapay Zeka Önerisi</strong><br>{kayit.genel_tavsiye}</div>",
            unsafe_allow_html=True,
        )

        if st.button("← Geri Dön & Değiştir"):
            st.caption("Değişiklik için 'Plan Oluştur' sekmesine geçebilirsin.")

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
with tab_rapor:
    st.markdown("<div class='fd-header'>📊 Verim &amp; Erteleme Raporu</div>", unsafe_allow_html=True)
    st.markdown("<div class='fd-card'>", unsafe_allow_html=True)

    rapor = report_service.haftalik_rapor()
    r_bitis = date.today()
    r_baslangic = r_bitis - timedelta(days=6)
    st.markdown(
        f"<div class='fd-info-card'>"
        f"<span style='color:#898781;'>Bu Hafta — {r_baslangic.day} {AYLAR[r_baslangic.month - 1]} / "
        f"{r_bitis.day} {AYLAR[r_bitis.month - 1]}</span><br>"
        f"<strong style='font-size:1.2rem;'>Haftalık Performans</strong></div>",
        unsafe_allow_html=True,
    )

    tcol1, tcol2 = st.columns(2)
    tcol1.markdown(
        f"<div class='fd-stat-tile' style='background:{RENK_IYI}; color:#fff;'>"
        f"<span class='deger'>%{rapor['verimlilik_orani']}</span>"
        f"<span class='etiket'>Verimlilik Oranı</span></div>",
        unsafe_allow_html=True,
    )
    tcol2.markdown(
        f"<div class='fd-stat-tile' style='background:{RENK_UYARI}; color:#0b0b0b;'>"
        f"<span class='deger'>%{rapor['erteleme_orani']}</span>"
        f"<span class='etiket'>Erteleme Oranı</span></div>",
        unsafe_allow_html=True,
    )
    tcol3, tcol4 = st.columns(2)
    tcol3.markdown(
        f"<div class='fd-stat-tile' style='background:{RENK_MAVI}; color:#fff;'>"
        f"<span class='deger'>{rapor['tamamlanan_sayisi']}</span>"
        f"<span class='etiket'>Tamamlanan Görev</span></div>",
        unsafe_allow_html=True,
    )
    tcol4.markdown(
        f"<div class='fd-stat-tile' style='background:{RENK_KRITIK}; color:#fff;'>"
        f"<span class='deger'>{rapor['ertelenen_sayisi']}</span>"
        f"<span class='etiket'>Ertelenen Görev</span></div>",
        unsafe_allow_html=True,
    )

    st.subheader("⏱️ Saat Dilimine Göre Verim")
    for etiket, yuzde in rapor["saat_dilimi_verimi"].items():
        bc1, bc2 = st.columns([1, 5])
        bc1.markdown(f"<span style='color:#52514e;'>{etiket}</span>", unsafe_allow_html=True)
        bc2.markdown(
            f"<div class='fd-bucket-track'><div class='fd-bucket-fill' style='width:{yuzde}%;'></div></div>"
            f"<span style='color:#52514e; font-size:0.8rem;'>%{yuzde}</span>",
            unsafe_allow_html=True,
        )

    st.subheader("🔁 En Çok Ertelenen Görevler")
    if not rapor["en_cok_ertelenenler"]:
        st.caption("Henüz ertelenen görev yok.")
    for satir in rapor["en_cok_ertelenenler"]:
        st.markdown(f"<div class='fd-gorev-row'>{satir}</div>", unsafe_allow_html=True)

    st.markdown(
        f"<div class='fd-analiz-kutu'>💡 <strong>Yapay Zeka Analizi</strong><br>{rapor['analiz_metni']}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)
