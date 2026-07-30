import html
import json
import logging
from datetime import date, datetime, time as dt_time, timedelta

import streamlit as st

from core.logging_config import setup_logging
from core.services import (
    degerlendirme_service,
    enerji_service,
    export_service,
    haftalik_blok_service,
    planning_service,
    profil_service,
    report_service,
    rutin_service,
    sync_service,
    user_service,
)
from core.services.planning_service import GUN_BASLANGIC, GUN_BITIS
from core.services.task_service import (
    complete_task,
    create_task,
    delete_task,
    gecikmis_gorevleri_listele,
    havuzdaki_gorevleri_listele,
    list_tasks,
    update_task,
)

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(page_title="FlowDay", layout="wide")

# ---------------------------------------------------------------------------
# Giriş / Kayıt — çoklu kullanıcı sistemi, her kullanıcı kendi hesabıyla girer.
# ---------------------------------------------------------------------------
if not st.session_state.get("user_id"):
    st.markdown(
        "<h2 style='text-align:center; margin-top:80px;'>🔒 FlowDay</h2>", unsafe_allow_html=True
    )
    _giris_col1, _giris_col2, _giris_col3 = st.columns([1, 1, 1])
    with _giris_col2:
        giris_tab, kayit_tab = st.tabs(["Giriş Yap", "Kayıt Ol"])
        with giris_tab:
            with st.form("giris_formu"):
                g_kullanici_adi = st.text_input("Kullanıcı adı")
                g_sifre = st.text_input("Parola", type="password")
                if st.form_submit_button("Giriş Yap", width="stretch"):
                    kullanici = user_service.authenticate(g_kullanici_adi, g_sifre)
                    if kullanici:
                        st.session_state["user_id"] = kullanici.id
                        st.session_state["is_admin"] = kullanici.is_admin
                        st.session_state["username"] = kullanici.username
                        st.rerun()
                    else:
                        logger.warning("Başarısız giriş denemesi: %s", g_kullanici_adi)
                        st.error("Kullanıcı adı veya parola hatalı")
        with kayit_tab:
            with st.form("kayit_formu"):
                k_kullanici_adi = st.text_input("Kullanıcı adı", key="kayit_ka")
                k_sifre = st.text_input("Parola", type="password", key="kayit_sifre")
                if st.form_submit_button("Kayıt Ol", width="stretch"):
                    try:
                        kullanici = user_service.create_user(k_kullanici_adi, k_sifre)
                        st.session_state["user_id"] = kullanici.id
                        st.session_state["is_admin"] = kullanici.is_admin
                        st.session_state["username"] = kullanici.username
                        st.rerun()
                    except ValueError as e:
                        logger.warning("Kayıt hatası: %s", e)
                        st.error(str(e))
    st.stop()

current_user_id = st.session_state["user_id"]

# ---------------------------------------------------------------------------
# Renkler — dataviz skill'inin durum paletinden (good/warning/critical) +
# kategorik mavi/mor. Orijinal FlowDay mockup'undaki mor-indigo gradyan
# kimliğini yaklaşık olarak uygulayan bir CSS katmanı (piksel-mükemmel değil),
# açık/koyu Streamlit temasına uyumlu.
# ---------------------------------------------------------------------------
RENK_IYI = "#0ca30c"
RENK_UYARI = "#c98500"
RENK_MAVI = "#2a78d6"
RENK_KRITIK = "#d03b3b"
RENK_MOR = "#4a3aa7"
GRADYAN = f"linear-gradient(135deg, {RENK_MOR} 0%, {RENK_MAVI} 100%)"

# Yumuşak-ton (tinted) yüzeyler: doygun renk yerine yarı-saydam ton + renkli metin —
# daha minimal/flat bir okunabilirlik için (Notion/Linear tarzı "callout" deseni).
# rgba (hex değil) kullanılıyor ki altındaki kart açık/koyu temaya göre otomatik uyum sağlasın.
RENK_IYI_TON = "rgba(12,163,12,0.14)"
RENK_UYARI_TON = "rgba(201,133,0,0.16)"
RENK_MAVI_TON = "rgba(42,120,214,0.14)"
RENK_KRITIK_TON = "rgba(208,59,59,0.14)"

ONCELIK_ETIKET = {3: "KRİTİK", 2: "ORTA", 1: "DÜŞÜK"}
ONCELIK_RENK = {3: RENK_KRITIK, 2: RENK_UYARI, 1: RENK_IYI}
ONCELIK_TON = {3: RENK_KRITIK_TON, 2: RENK_UYARI_TON, 1: RENK_IYI_TON}
ENERJI_ETIKETLERI = {"dusuk": "😴 Düşük", "orta": "🙂 Orta", "yuksek": "⚡ Yüksek"}

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
GUN_KISALTMALARI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


# ---------------------------------------------------------------------------
# "AI Planı" sekmesindeki saat-eksenli görsel çizelge için salt sunum
# amaçlı yardımcılar — iş mantığı içermez, planning_service'teki yerleştirme
# algoritmasına dokunmaz.
# ---------------------------------------------------------------------------
def _gun_dakikasi(t: dt_time) -> int:
    return t.hour * 60 + t.minute


def _saat_metni_dakikaya(saat_metni: str) -> int:
    saat, dakika = saat_metni.split(":")
    return int(saat) * 60 + int(dakika)


def _guvenli_metin(metin: str) -> str:
    """Kullanıcı girdisini unsafe_allow_html içine güvenle gömmek için kaçışlar."""
    return html.escape(metin)


def _konum_link_satiri(task) -> str:
    """Görev kartında opsiyonel konum/link bilgisini gösteren küçük bir HTML parçası üretir."""
    parcalar = []
    if task.konum:
        parcalar.append(f"📍 {_guvenli_metin(task.konum)}")
    if task.link:
        temiz_link = task.link.strip()
        if temiz_link.lower().startswith(("http://", "https://")):
            href = html.escape(temiz_link, quote=True)
            parcalar.append(f"🔗 <a href='{href}' target='_blank' rel='noopener noreferrer'>Link</a>")
        else:
            parcalar.append(f"🔗 {_guvenli_metin(temiz_link)}")
    return " · " + " · ".join(parcalar) if parcalar else ""


def _gorev_satirini_ciz(task, current_user_id: int, secili_gun: date, profil) -> None:
    """Tek bir görev satırını (rozetler, tamamla/düzenle/sil butonları, düzenleme formu) çizer.

    `gunun_gorevleri` ve `havuzdaki_gorevler` listeleri hiçbir zaman aynı task.id'yi
    paylaşmaz (biri due_date=secili_gun, diğeri due_date=None ister) — bu yüzden aynı
    fonksiyon iki farklı listede de widget key çakışması olmadan kullanılabilir.
    """
    c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
    tamamlandi_isareti = " ✓" if task.done else ""
    kesin_rozeti = (
        f"<span class='fd-rozet' style='background:{RENK_KRITIK_TON}; color:{RENK_KRITIK};'>KESİN</span>"
        if task.teslim_tipi == "kesin" else ""
    )
    rutin_rozeti = (
        f"<span class='fd-rozet' style='background:{RENK_MAVI_TON}; color:{RENK_MAVI};'>🔁 RUTİN</span>"
        if task.rutin_id is not None else ""
    )
    c1.markdown(
        f"<div class='fd-gorev-row'>"
        f"<span class='fd-rozet' style='background:{ONCELIK_TON[task.priority]}; "
        f"color:{ONCELIK_RENK[task.priority]};'>{ONCELIK_ETIKET[task.priority]}</span>"
        f"{kesin_rozeti}{rutin_rozeti}"
        f"<strong>{_guvenli_metin(task.title)}{tamamlandi_isareti}</strong>"
        f"<br><span style='color:#898781; font-size:0.85rem;'>⏱ {task.duration_minutes} dakika"
        f" · 🔁 {task.postponement_count} kez ertelendi"
        f"{_konum_link_satiri(task)}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if task.postponement_count >= planning_service.ERTELEME_ONERI_ESIGI:
        st.caption(f"⚠️ {planning_service.erteleme_onerisi_uret(task, profil)}")
    if task.en_erken_baslangic is not None:
        st.caption(f"🚩 {task.en_erken_baslangic:%d.%m.%Y}'ten önce başlanamaz")
    if c2.button("✓", key=f"tamamla_{task.id}", disabled=task.done, help="Görevi tamamla"):
        complete_task(current_user_id, task.id)
        st.rerun()
    if c3.button("✎", key=f"duzenle_{task.id}", help="Görevi düzenle"):
        st.session_state["duzenle_id"] = None if st.session_state.get("duzenle_id") == task.id else task.id
        st.rerun()
    if c4.button("🗑", key=f"sil_{task.id}", help="Görevi sil"):
        delete_task(current_user_id, task.id)
        st.rerun()

    if st.session_state.get("duzenle_id") == task.id:
        with st.form(f"duzenle_form_{task.id}"):
            e_title = st.text_input("Başlık", value=task.title)
            e_sure = st.number_input("Süre (dakika)", min_value=1, value=task.duration_minutes)
            e_oncelik = st.selectbox(
                "Öncelik", options=[3, 2, 1], index=[3, 2, 1].index(task.priority),
                format_func=lambda p: ONCELIK_ETIKET[p],
            )
            e_konum = st.text_input("📍 Konum (opsiyonel)", value=task.konum)
            e_link = st.text_input("🔗 Link (opsiyonel)", value=task.link)
            e_teslim_tipi = st.selectbox(
                "Teslim Tipi", options=["Esnek", "Kesin"],
                index=["esnek", "kesin"].index(task.teslim_tipi),
            )
            e_kesin_tarih = e_kesin_saat = None
            if e_teslim_tipi == "Kesin":
                varsayilan_kesin = task.kesin_bitis or datetime.combine(
                    task.due_date or secili_gun, dt_time(18, 0)
                )
                etcol1, etcol2 = st.columns(2)
                e_kesin_tarih = etcol1.date_input("Kesin bitiş tarihi", value=varsayilan_kesin.date())
                e_kesin_saat = etcol2.time_input("Kesin bitiş saati", value=varsayilan_kesin.time())
                if (
                    task.teslim_tipi == "kesin" and task.kesin_bitis is not None
                    and datetime.combine(e_kesin_tarih, e_kesin_saat) > task.kesin_bitis
                ):
                    st.warning(
                        "⚠️ Bu görev kesin teslimli — ertelemek önerilmez. "
                        "Yeniden planlamada yine de önce yerleştirilecek."
                    )
                e_due = e_kesin_tarih
            else:
                e_due = st.date_input("Son tarih", value=task.due_date or secili_gun)
            e_en_erken_var = st.checkbox(
                "🚩 En erken başlangıç tarihi belirle", value=task.en_erken_baslangic is not None,
            )
            e_en_erken = None
            if e_en_erken_var:
                e_en_erken = st.date_input(
                    "En erken başlangıç tarihi", value=task.en_erken_baslangic or (task.due_date or secili_gun),
                )
            if st.form_submit_button("Kaydet"):
                try:
                    kesin_bitis = (
                        datetime.combine(e_kesin_tarih, e_kesin_saat)
                        if e_teslim_tipi == "Kesin" else None
                    )
                    update_task(
                        current_user_id, task.id, e_title, task.description, e_oncelik, e_due, e_sure,
                        konum=e_konum, link=e_link,
                        teslim_tipi="kesin" if e_teslim_tipi == "Kesin" else "esnek",
                        kesin_bitis=kesin_bitis,
                        en_erken_baslangic=e_en_erken,
                    )
                    st.session_state["duzenle_id"] = None
                    st.toast("Görev güncellendi", icon="✅")
                    st.rerun()
                except ValueError as e:
                    logger.warning("Görev düzenleme hatası: %s", e)
                    st.error(str(e))


def _uyku_bloklari_gun_icinde(uyku_baslangic: dt_time, uyku_bitis: dt_time) -> list[tuple[int, int]]:
    """Uyku penceresini GUN_BASLANGIC–GUN_BITIS sınırlarına kırpar (gece yarısı sarma dahil)."""
    gun_b, gun_e = _gun_dakikasi(GUN_BASLANGIC), _gun_dakikasi(GUN_BITIS)
    b, e = _gun_dakikasi(uyku_baslangic), _gun_dakikasi(uyku_bitis)
    if b == e:
        return []
    parcalar = [(b, e)] if b < e else [(b, 24 * 60), (0, e)]
    sonuc = []
    for p_b, p_e in parcalar:
        kirpilmis_b, kirpilmis_e = max(p_b, gun_b), min(p_e, gun_e)
        if kirpilmis_b < kirpilmis_e:
            sonuc.append((kirpilmis_b, kirpilmis_e))
    return sonuc

with st.sidebar:
    _kullanici_adi = st.session_state.get("username", "")
    _admin_rozeti = (
        "<br><span class='fd-badge' style='background:rgba(74,58,167,0.14); color:#4a3aa7; margin-top:2px;'>🛠️ Admin</span>"
        if st.session_state.get("is_admin") else ""
    )
    st.markdown(
        f"<div style='display:flex; align-items:center; gap:10px;'>"
        f"<div class='fd-avatar-sm'>{(_kullanici_adi or '?')[0].upper()}</div>"
        f"<div><strong>{_kullanici_adi}</strong>{_admin_rozeti}</div></div>",
        unsafe_allow_html=True,
    )
    _bugun = date.today()
    st.caption(f"📅 {_bugun.day} {AYLAR[_bugun.month - 1]} {_bugun.year}")
    _bugunku_gorevler = list_tasks(current_user_id, due_date=date.today())
    if _bugunku_gorevler:
        _tamamlanan_sayi = sum(1 for t in _bugunku_gorevler if t.done)
        _tamamlanma_yuzdesi = round(_tamamlanan_sayi / len(_bugunku_gorevler) * 100)
        st.markdown(
            f"<span style='font-size:0.82rem; color:#898781;'>"
            f"Bugün {_tamamlanan_sayi}/{len(_bugunku_gorevler)} görev tamamlandı</span>"
            f"<div class='fd-bucket-track' style='height:6px; margin-top:5px;'>"
            f"<div class='fd-bucket-fill' style='height:6px; width:{_tamamlanma_yuzdesi}%;'></div></div>",
            unsafe_allow_html=True,
        )
    st.divider()
    if st.button("🚪 Çıkış Yap", width="stretch", key="sidebar_cikis"):
        for anahtar in ("user_id", "is_admin", "username"):
            st.session_state.pop(anahtar, None)
        st.rerun()

_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
@keyframes fdFadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}
.stApp {
    background: #f6f6f8;
}
@media (prefers-color-scheme: dark) {
    .stApp { background: #101013; }
}
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    background: #ffffff;
    padding: 5px;
    border-radius: 12px;
    border: 1px solid rgba(11,11,11,0.06);
}
@media (prefers-color-scheme: dark) {
    .stTabs [data-baseweb="tab-list"] { background: #18181e; border-color: rgba(255,255,255,0.07); }
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 7px 14px;
    transition: background 0.15s ease;
}
.stTabs [aria-selected="true"] {
    background: __GRADYAN__ !important;
}
.stTabs [aria-selected="true"] p {
    color: #ffffff !important;
    font-weight: 600;
}
div.stButton > button, div.stDownloadButton > button, div[data-testid="stFormSubmitButton"] > button {
    border-radius: 8px;
    transition: border-color 0.15s ease, background 0.15s ease, transform 0.12s ease, box-shadow 0.12s ease;
}
div.stButton > button:hover, div.stDownloadButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 3px 8px rgba(11,11,11,0.10);
}
div.stButton > button:active, div.stDownloadButton > button:active, div[data-testid="stFormSubmitButton"] > button:active {
    transform: translateY(0);
    box-shadow: none;
}
div.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: __GRADYAN__;
    border: none;
}
.fd-header {
    background: __RENK_MOR__;
    color: #ffffff;
    padding: 14px 20px;
    border-radius: 12px 12px 0 0;
    font-size: 1.05rem;
    font-weight: 600;
    margin-top: 8px;
    letter-spacing: 0.1px;
}
.fd-card {
    background: #ffffff;
    border-radius: 0 0 12px 12px;
    padding: 20px;
    box-shadow: 0 1px 2px rgba(11,11,11,0.04);
    margin-bottom: 24px;
    border: 1px solid rgba(11,11,11,0.06);
    border-top: none;
    animation: fdFadeIn 0.25s ease;
}
@media (prefers-color-scheme: dark) {
    .fd-card {
        background: #16161b;
        box-shadow: none;
        border-color: rgba(255,255,255,0.08);
        color: #e7e6f0;
    }
}
.fd-avatar {
    width: 64px; height: 64px; border-radius: 50%;
    background: __GRADYAN__; color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.25rem; font-weight: 600; margin: 0 auto 12px auto;
    transition: transform 0.2s ease;
}
.fd-avatar:hover { transform: scale(1.06); }
.fd-avatar-sm {
    width: 38px; height: 38px; border-radius: 50%;
    background: __GRADYAN__; color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem; font-weight: 600; flex-shrink: 0;
}
.fd-stat-tile {
    border-radius: 10px; padding: 18px; text-align: center;
    font-weight: 700; margin-bottom: 12px;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.fd-stat-tile:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 10px rgba(11,11,11,0.08);
}
@media (prefers-color-scheme: dark) {
    .fd-stat-tile:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.4); }
}
.fd-stat-tile .deger { font-size: 1.7rem; display: block; }
.fd-stat-tile .etiket { font-size: 0.82rem; font-weight: 500; opacity: 0.85; }
.fd-info-card {
    background: #f7f7f9; border-radius: 10px; padding: 14px 18px; margin-bottom: 14px;
    border: 1px solid rgba(11,11,11,0.05);
}
@media (prefers-color-scheme: dark) {
    .fd-info-card { background: #1c1c22; border-color: rgba(255,255,255,0.07); color: #e7e6f0; }
}
.fd-badge {
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600;
}
.fd-blok-row, .fd-gorev-row {
    border-left: 3px solid __RENK_MAVI__; background: #f7f7f9;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 6px;
    transition: background 0.15s ease;
}
.fd-blok-row:hover, .fd-gorev-row:hover { background: #f0eff5; }
@media (prefers-color-scheme: dark) {
    .fd-blok-row, .fd-gorev-row { background: #1c1c22; color: #e7e6f0; }
    .fd-blok-row:hover, .fd-gorev-row:hover { background: #232329; }
}
.fd-rozet {
    display: inline-block; padding: 2px 9px; border-radius: 5px;
    font-size: 0.72rem; font-weight: 700; margin-right: 8px;
}
.fd-dilim-card {
    background: #f7f7f9; border-left: 3px solid __RENK_MOR__;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;
}
@media (prefers-color-scheme: dark) { .fd-dilim-card { background: #1c1c22; color: #e7e6f0; } }
.fd-oneri-kutu {
    background: rgba(12,163,12,0.08); border-radius: 10px; padding: 16px 20px; margin-top: 14px;
    border-left: 3px solid __RENK_IYI__;
}
@media (prefers-color-scheme: dark) {
    .fd-oneri-kutu { background: rgba(12,163,12,0.14); color: #e7e6f0; }
}
.fd-analiz-kutu {
    background: rgba(42,120,214,0.08); border-radius: 10px; padding: 16px 20px; margin-top: 14px;
    border-left: 3px solid __RENK_MAVI__;
}
@media (prefers-color-scheme: dark) {
    .fd-analiz-kutu { background: rgba(42,120,214,0.16); color: #e7e6f0; }
}
.fd-bucket-track {
    background: #ececf1; border-radius: 999px; height: 20px; overflow: hidden;
}
@media (prefers-color-scheme: dark) { .fd-bucket-track { background: #26262d; } }
.fd-bucket-fill {
    background: __RENK_MAVI__; border-radius: 999px; height: 20px;
    transition: width 0.5s ease;
}
.fd-empty {
    text-align: center; padding: 32px 20px; color: #898781;
}
.fd-empty .fd-empty-icon {
    font-size: 1.8rem; display: block; margin-bottom: 8px; opacity: 0.6;
}
.fd-zaman-cizelgesi {
    position: relative;
    margin-left: 52px;
    border-left: 1px solid rgba(11,11,11,0.08);
    background-image: repeating-linear-gradient(
        to bottom,
        rgba(11,11,11,0.06) 0, rgba(11,11,11,0.06) 1px,
        transparent 1px, transparent 60px
    );
}
@media (prefers-color-scheme: dark) {
    .fd-zaman-cizelgesi {
        border-left-color: rgba(255,255,255,0.10);
        background-image: repeating-linear-gradient(
            to bottom,
            rgba(255,255,255,0.08) 0, rgba(255,255,255,0.08) 1px,
            transparent 1px, transparent 60px
        );
    }
}
.fd-zaman-etiket {
    position: absolute; left: -52px; width: 44px; text-align: right;
    font-size: 0.72rem; color: #898781; transform: translateY(-6px);
}
.fd-zaman-uyku {
    position: absolute; left: 4px; right: 4px;
    background: rgba(137,135,129,0.12);
    border-radius: 6px;
    font-size: 0.72rem; color: #898781;
    padding: 2px 8px; box-sizing: border-box;
}
@media (prefers-color-scheme: dark) {
    .fd-zaman-uyku { background: rgba(255,255,255,0.05); }
}
.fd-zaman-blok {
    position: absolute; left: 4px; right: 4px;
    border-radius: 6px; border-left: 3px solid;
    padding: 3px 8px; box-sizing: border-box;
    overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
    font-size: 0.78rem; font-weight: 600;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.fd-zaman-blok:hover {
    transform: scale(1.01);
    box-shadow: 0 2px 8px rgba(11,11,11,0.12);
    z-index: 2;
}
.fd-zaman-simdi {
    position: absolute; left: 0; right: 4px; height: 2px;
    background: __RENK_KRITIK__; z-index: 3;
}
.fd-zaman-simdi::before {
    content: ""; position: absolute; left: -5px; top: -4px;
    width: 8px; height: 8px; border-radius: 50%; background: __RENK_KRITIK__;
}
</style>
"""
_STYLE = (
    _STYLE.replace("__GRADYAN__", GRADYAN)
    .replace("__RENK_IYI__", RENK_IYI)
    .replace("__RENK_MAVI__", RENK_MAVI)
    .replace("__RENK_MOR__", RENK_MOR)
    .replace("__RENK_KRITIK__", RENK_KRITIK)
)
st.markdown(_STYLE, unsafe_allow_html=True)

st.markdown(
    "<h1 style='text-align:center; margin-bottom:0; letter-spacing:-0.5px;'>🎯 FlowDay</h1>"
    "<p style='text-align:center; color:#898781; margin-top:4px; font-size:0.95rem;'>"
    "Dinamik Günlük Planlayıcı</p>",
    unsafe_allow_html=True,
)

_sekme_etiketleri = ["👤 Profil", "📝 Plan Oluştur", "🗓️ AI Planı", "📊 Rapor"]
if st.session_state.get("is_admin"):
    _sekme_etiketleri.append("🛠️ Admin")
_sekmeler = st.tabs(_sekme_etiketleri)
tab_profil, tab_plan, tab_ai, tab_rapor = _sekmeler[:4]
tab_admin = _sekmeler[4] if len(_sekmeler) > 4 else None

# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------
with tab_profil:
    st.markdown("<div class='fd-header'>👤 Profil &amp; Ayarlar</div>", unsafe_allow_html=True)
    st.markdown("<div class='fd-card'>", unsafe_allow_html=True)

    profil = profil_service.get_or_create(current_user_id)
    baslangic_harfleri = "".join(p[0].upper() for p in profil.ad_soyad.split()[:2]) or "?"
    st.markdown(
        f"<div class='fd-avatar'>{baslangic_harfleri}</div>"
        f"<p style='text-align:center; font-weight:700; margin-bottom:0;'>{profil.ad_soyad or st.session_state['username']}</p>"
        f"<p style='text-align:center; color:#898781; margin-top:0;'>{profil.e_posta or '—'}</p>",
        unsafe_allow_html=True,
    )

    profil_widget_surumu = st.session_state.get("profil_widget_surumu", 0)
    with st.form("profil_form"):
        p_ad = st.text_input("👤 Ad Soyad", value=profil.ad_soyad)
        p_eposta = st.text_input("✉️ E-posta", value=profil.e_posta)
        st.caption("⚡ En Verimli Olduğun Saatler")
        col1, col2 = st.columns(2)
        p_verimli_b = col1.time_input(
            "Başlangıç", value=profil.verimli_baslangic, key=f"p_verimli_b_{profil_widget_surumu}",
        )
        p_verimli_e = col2.time_input(
            "Bitiş", value=profil.verimli_bitis, key=f"p_verimli_e_{profil_widget_surumu}",
        )
        st.caption("😴 Varsayılan Uyku Saatleri")
        col3, col4 = st.columns(2)
        p_uyku_b = col3.time_input("Başlangıç", value=profil.uyku_baslangic, key="p_uyku_b")
        p_uyku_e = col4.time_input("Bitiş", value=profil.uyku_bitis, key="p_uyku_e")
        p_hedef = st.number_input("🎯 Günlük Hedef (görev sayısı)", min_value=1, value=profil.gunluk_hedef)
        p_buffer = st.number_input(
            "⏱️ Görevler Arası Boşluk (dakika)", min_value=0, value=profil.buffer_dakika,
            help="Plan oluşturulurken her görevden sonra bu kadar dakika boşluk bırakılır.",
        )

        if st.form_submit_button("💾 Kaydet", type="primary", width="stretch"):
            try:
                profil_service.save(
                    current_user_id, p_ad, p_eposta, p_verimli_b, p_verimli_e, p_uyku_b, p_uyku_e, p_hedef,
                    p_buffer,
                )
                st.toast("Profil kaydedildi", icon="✅")
                st.rerun()
            except ValueError as e:
                logger.warning("Profil kaydetme hatası: %s", e)
                st.error(str(e))

    st.divider()
    st.subheader("🔁 Rutinler")
    st.caption(
        "Haftalık tekrarlayan görevler — belirlediğin gün ve saatte otomatik olarak "
        "günlük plana eklenir."
    )

    rutinler = rutin_service.list_rutinler(current_user_id)
    if not rutinler:
        st.markdown(
            "<div class='fd-empty'><span class='fd-empty-icon'>🔁</span>"
            "Henüz rutin eklenmedi.</div>",
            unsafe_allow_html=True,
        )
    for rutin in rutinler:
        gunler_metni = ", ".join(GUN_KISALTMALARI[g] for g in rutin.gunler)
        rc1, rc2, rc3 = st.columns([4, 1, 1])
        pasif_notu = " · pasif" if not rutin.aktif else ""
        rc1.markdown(
            f"<div class='fd-gorev-row'>"
            f"<span class='fd-rozet' style='background:{ONCELIK_TON[rutin.oncelik]}; "
            f"color:{ONCELIK_RENK[rutin.oncelik]};'>{ONCELIK_ETIKET[rutin.oncelik]}</span>"
            f"<strong>{_guvenli_metin(rutin.baslik)}</strong>"
            f"<br><span style='color:#898781; font-size:0.85rem;'>{gunler_metni} · "
            f"{rutin.saat:%H:%M} · {rutin.sure_dakika} dk{pasif_notu}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if rc2.button("Pasif Yap" if rutin.aktif else "Aktif Yap", key=f"rutin_toggle_{rutin.id}"):
            rutin_service.update_rutin(
                current_user_id, rutin.id, rutin.baslik, rutin.gunler, rutin.saat,
                rutin.sure_dakika, rutin.oncelik, aktif=not rutin.aktif,
            )
            st.rerun()
        if rc3.button("Sil", key=f"rutin_sil_{rutin.id}"):
            rutin_service.delete_rutin(current_user_id, rutin.id)
            st.toast(f"'{rutin.baslik}' rutini silindi", icon="🗑️")
            st.rerun()
        rutin_onerisi = rutin_service.rutin_erteleme_onerisi(current_user_id, rutin.id)
        if rutin_onerisi:
            st.caption(f"⚠️ {rutin_onerisi}")

    with st.form("yeni_rutin_formu", clear_on_submit=True):
        r_baslik = st.text_input("Başlık (ör: Spor)", key="r_baslik")
        r_gunler_secim = st.multiselect(
            "Günler", options=list(range(7)), format_func=lambda g: GUN_KISALTMALARI[g], key="r_gunler"
        )
        rcol1, rcol2, rcol3 = st.columns(3)
        r_saat = rcol1.time_input("Saat", value=dt_time(18, 0), key="r_saat")
        r_sure = rcol2.number_input("Süre (dakika)", min_value=1, value=30, key="r_sure")
        r_oncelik = rcol3.selectbox(
            "Öncelik", options=[3, 2, 1], format_func=lambda p: ONCELIK_ETIKET[p], key="r_oncelik"
        )
        if st.form_submit_button("+ Rutin Ekle"):
            try:
                rutin_service.create_rutin(
                    current_user_id, r_baslik, r_gunler_secim, r_saat, r_sure, r_oncelik
                )
                st.toast(f"'{r_baslik}' rutini eklendi", icon="✅")
                st.rerun()
            except ValueError as e:
                logger.warning("Rutin oluşturma hatası: %s", e)
                st.error(str(e))

    st.divider()
    st.subheader("🔒 Sabit Kapalı & Serbest Zamanlar")
    st.caption(
        "Haftalık tekrar eden, kalıcı meşgul zamanlar (ör. ders) veya korunan kişisel "
        "zamanlar (ör. hobi) — Plan Oluştur'da ilgili güne otomatik eklenir."
    )

    TUR_ETIKETLERI = {"sabit_kapali": "🔒 Sabit Kapalı", "serbest": "🌿 Serbest Zaman"}
    bloklar = haftalik_blok_service.list_bloklar(current_user_id)
    if not bloklar:
        st.markdown(
            "<div class='fd-empty'><span class='fd-empty-icon'>🔒</span>"
            "Henüz kalıcı blok eklenmedi.</div>",
            unsafe_allow_html=True,
        )
    for blok in bloklar:
        bc1, bc2 = st.columns([5, 1])
        bc1.markdown(
            f"<div class='fd-blok-row'>{TUR_ETIKETLERI[blok.tur]} · {_guvenli_metin(blok.etiket) or '—'}"
            f"<br><span style='color:#898781; font-size:0.85rem;'>"
            f"{GUNLER[blok.gun]} {blok.baslangic:%H:%M}–{blok.bitis:%H:%M}</span></div>",
            unsafe_allow_html=True,
        )
        if bc2.button("Sil", key=f"blok_sil_{blok.id}"):
            haftalik_blok_service.delete_blok(current_user_id, blok.id)
            st.toast("Blok silindi", icon="🗑️")
            st.rerun()

    with st.form("yeni_haftalik_blok_formu", clear_on_submit=True):
        hb_tur = st.selectbox(
            "Tür", options=["sabit_kapali", "serbest"], format_func=lambda t: TUR_ETIKETLERI[t], key="hb_tur"
        )
        hb_gunler_secim = st.multiselect(
            "Günler", options=list(range(7)), format_func=lambda g: GUN_KISALTMALARI[g], key="hb_gunler"
        )
        hbcol1, hbcol2, hbcol3 = st.columns(3)
        hb_baslangic = hbcol1.time_input("Başlangıç", value=dt_time(9, 0), key="hb_baslangic")
        hb_bitis = hbcol2.time_input("Bitiş", value=dt_time(12, 0), key="hb_bitis")
        hb_etiket = hbcol3.text_input("Etiket", key="hb_etiket", placeholder="ör: Ders")
        if st.form_submit_button("+ Ekle"):
            try:
                if not hb_gunler_secim:
                    raise ValueError("En az bir gün seçmelisin")
                for gun in hb_gunler_secim:
                    haftalik_blok_service.create_blok(
                        current_user_id, hb_tur, gun, hb_baslangic, hb_bitis, hb_etiket
                    )
                st.toast("Blok(lar) eklendi", icon="✅")
                st.rerun()
            except ValueError as e:
                logger.warning("Haftalık blok oluşturma hatası: %s", e)
                st.error(str(e))

    st.divider()
    st.subheader("🗂️ Veri Yönetimi")
    st.caption("Tüm görevlerini, takvim etkinliklerini, profilini ve plan geçmişini tek bir JSON dosyası olarak indir.")
    yedek = export_service.tum_veriyi_disa_aktar(current_user_id)
    st.download_button(
        "📦 Verilerini İndir (JSON)",
        data=json.dumps(yedek, ensure_ascii=False, indent=2),
        file_name=f"flowday_yedek_{date.today():%Y-%m-%d}.json",
        mime="application/json",
    )

    st.divider()
    st.subheader("⚠️ Hesabı Sil")
    st.caption("Hesabını ve tüm görev/etkinlik/profil/plan verini kalıcı olarak siler. Bu işlem geri alınamaz.")
    kendi_hesap_onay = st.checkbox(
        "Hesabımı kalıcı olarak silmek istediğimi onaylıyorum", key="kendi_hesap_silme_onay"
    )
    if st.button("🗑️ Hesabımı Kalıcı Olarak Sil", disabled=not kendi_hesap_onay, key="kendi_hesap_sil"):
        try:
            user_service.delete_user(current_user_id)
            for anahtar in ("user_id", "is_admin", "username"):
                st.session_state.pop(anahtar, None)
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Plan Oluştur — iki kolon: solda gün ayarları, sağda görev listesi
# ---------------------------------------------------------------------------
with tab_plan:
    st.markdown("<div class='fd-header'>📝 Günlük Plan Oluştur</div>", unsafe_allow_html=True)
    st.markdown("<div class='fd-card'>", unsafe_allow_html=True)

    profil = profil_service.get_or_create(current_user_id)
    secili_gun = st.date_input(
        "📅 Günü Seç", value=st.session_state.get("secili_gun", date.today()), key="secili_gun"
    )
    rutin_service.haftalik_rutinleri_uret(current_user_id, secili_gun)

    mevcut_enerji = enerji_service.get_enerji_seviyesi(current_user_id, secili_gun) or "orta"
    enerji_secimi = st.selectbox(
        "⚡ Bugün enerjin nasıl?", options=["dusuk", "orta", "yuksek"],
        index=["dusuk", "orta", "yuksek"].index(mevcut_enerji),
        format_func=lambda s: ENERJI_ETIKETLERI[s], key=f"enerji_{secili_gun}",
    )
    if enerji_secimi != mevcut_enerji:
        enerji_service.set_enerji_seviyesi(current_user_id, secili_gun, enerji_secimi)

    if st.session_state.get("bloklar_gun") != secili_gun:
        kalici_bloklar = haftalik_blok_service.list_bloklar(current_user_id, gun=secili_gun.weekday())
        st.session_state["uygun_olmayan_bloklar"] = [
            {"start": profil.uyku_baslangic, "end": profil.uyku_bitis, "label": "😴 Uyku Saati"}
        ] + [
            {
                "start": b.baslangic, "end": b.bitis,
                "label": f"{'🔒' if b.tur == 'sabit_kapali' else '🌿'} "
                         f"{b.etiket or ('Sabit Kapalı' if b.tur == 'sabit_kapali' else 'Serbest Zaman')}",
            }
            for b in kalici_bloklar
        ]
        st.session_state["bloklar_gun"] = secili_gun

    sol_kolon, sag_kolon = st.columns([1, 1.2], gap="large")

    with sol_kolon:
        if secili_gun >= date.today():
            gecikmisler = gecikmis_gorevleri_listele(current_user_id, date.today())
            if gecikmisler:
                st.subheader("⏰ Geçmişten Kalan Görevler")
                for gecikmis in gecikmisler:
                    gc1, gc2 = st.columns([5, 2])
                    gun_farki = (date.today() - gecikmis.due_date).days
                    gc1.markdown(
                        f"<div class='fd-gorev-row'>"
                        f"<span class='fd-rozet' style='background:{ONCELIK_TON[gecikmis.priority]}; "
                        f"color:{ONCELIK_RENK[gecikmis.priority]};'>{ONCELIK_ETIKET[gecikmis.priority]}</span>"
                        f"<strong>{gecikmis.title}</strong>"
                        f"<br><span style='color:#898781; font-size:0.85rem;'>{gun_farki} gündür gecikmiş</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if gc2.button(
                        f"→ {secili_gun:%d.%m}'e taşı", key=f"tasi_{gecikmis.id}",
                        help="Görevi seçili güne taşı",
                    ):
                        # Kesin teslimli görevlerde due_date, kesin_bitis'ten türetildiği için
                        # kesin_bitis'i de yeni güne taşımak gerekiyor (saat aynı kalır).
                        yeni_kesin_bitis = (
                            datetime.combine(secili_gun, gecikmis.kesin_bitis.time())
                            if gecikmis.teslim_tipi == "kesin" and gecikmis.kesin_bitis is not None
                            else None
                        )
                        update_task(
                            current_user_id, gecikmis.id, gecikmis.title, gecikmis.description, gecikmis.priority,
                            due_date=secili_gun, duration_minutes=gecikmis.duration_minutes,
                            konum=gecikmis.konum, link=gecikmis.link,
                            teslim_tipi=gecikmis.teslim_tipi, kesin_bitis=yeni_kesin_bitis,
                            en_erken_baslangic=gecikmis.en_erken_baslangic,
                        )
                        st.toast(f"'{gecikmis.title}' {secili_gun:%d.%m} gününe taşındı", icon="↪️")
                        st.rerun()

        st.subheader("🚫 Uygun Olmayan Saatler (Ders, Uyku vb.)")
        bcol1, bcol2 = st.columns(2)
        blok_bas = bcol1.time_input("Başlangıç", value=dt_time(9, 0), key="blok_bas")
        blok_bit = bcol2.time_input("Bitiş", value=dt_time(12, 0), key="blok_bit")
        blok_etiket = st.text_input("Etiket", key="blok_etiket", placeholder="ör: Ders")
        if st.button("+ Ekle", key="blok_ekle_btn"):
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

    with sag_kolon:
        st.subheader("📋 Yeni Kayıt")
        g_kayit_turu = st.selectbox("Kayıt Türü", options=["Görev", "Etkinlik"], key="g_kayit_turu")

        if g_kayit_turu == "Görev":
            g_title = st.text_input("İş adı (ör: Raporu yaz)", key="g_title")
            gcol1, gcol2 = st.columns(2)
            g_sure = gcol1.number_input("Süre (dakika)", min_value=1, value=30, key="g_sure")
            g_oncelik = gcol2.selectbox(
                "Öncelik Seç", options=[3, 2, 1], format_func=lambda p: ONCELIK_ETIKET[p], key="g_oncelik"
            )
            gcol3, gcol4 = st.columns(2)
            g_konum = gcol3.text_input("📍 Konum (opsiyonel)", key="g_konum")
            g_link = gcol4.text_input("🔗 Link (opsiyonel)", key="g_link")
            g_teslim_tipi = st.selectbox(
                "Teslim Tipi", options=["Esnek", "Kesin"], key="g_teslim_tipi",
                help="Esnek: planlama ertelenebilir/yeniden düzenlenebilir. Kesin: belirli bir tarih/saate kadar bitmeli.",
            )
            g_kesin_tarih = g_kesin_saat = None
            g_havuza_ekle = False
            if g_teslim_tipi == "Kesin":
                gtcol1, gtcol2 = st.columns(2)
                g_kesin_tarih = gtcol1.date_input("Kesin bitiş tarihi", value=secili_gun, key="g_kesin_tarih")
                g_kesin_saat = gtcol2.time_input("Kesin bitiş saati", value=dt_time(18, 0), key="g_kesin_saat")
            else:
                g_havuza_ekle = st.checkbox(
                    "📥 Son tarih belirtme (Havuza ekle)", key="g_havuza_ekle",
                    help="Bu görev belirli bir güne bağlanmaz, havuzda bekler; plan oluştururken boş kalan zamana otomatik eklenebilir.",
                )
            g_en_erken_var = st.checkbox("🚩 En erken başlangıç tarihi belirle", key="g_en_erken_var")
            g_en_erken = None
            if g_en_erken_var:
                g_en_erken = st.date_input("En erken başlangıç tarihi", value=secili_gun, key="g_en_erken")
            if st.button("+ Görev Ekle", type="primary", width="stretch"):
                try:
                    kesin_bitis = (
                        datetime.combine(g_kesin_tarih, g_kesin_saat) if g_teslim_tipi == "Kesin" else None
                    )
                    create_task(
                        current_user_id, g_title, priority=g_oncelik,
                        due_date=None if g_havuza_ekle else secili_gun, duration_minutes=g_sure,
                        konum=g_konum, link=g_link,
                        teslim_tipi="kesin" if g_teslim_tipi == "Kesin" else "esnek",
                        kesin_bitis=kesin_bitis,
                        en_erken_baslangic=g_en_erken,
                    )
                    st.toast(f"'{g_title}' eklendi", icon="✅")
                    st.rerun()
                except ValueError as e:
                    logger.warning("Görev oluşturma hatası: %s", e)
                    st.error(str(e))
        else:
            ev_title = st.text_input("Başlık", key="ev_baslik")
            ev_desc = st.text_area("Açıklama", height=80, key="ev_aciklama")
            ev_konum = st.text_input("📍 Konum (opsiyonel)", key="ev_konum")
            evcol1, evcol2, evcol3 = st.columns(3)
            ev_gun = evcol1.date_input("Tarih", value=secili_gun, key="ev_gun")
            ev_bas = evcol2.time_input("Başlangıç", value=dt_time(9, 0), key="ev_bas")
            ev_bit = evcol3.time_input("Bitiş", value=dt_time(10, 0), key="ev_bit")
            if st.button("+ Etkinlik Ekle (Google Takvim'e)", type="primary", width="stretch"):
                if not ev_title.strip():
                    st.error("Başlık boş olamaz")
                elif ev_bit <= ev_bas:
                    st.error("Bitiş, başlangıçtan sonra olmalı")
                else:
                    with st.spinner("Google Takvim'e ekleniyor..."):
                        start_iso = datetime.combine(ev_gun, ev_bas).astimezone().isoformat()
                        end_iso = datetime.combine(ev_gun, ev_bit).astimezone().isoformat()
                        sync_service.create_event_everywhere(
                            current_user_id, ev_title, start_iso, end_iso, ev_desc, ev_konum
                        )
                    st.toast("Etkinlik Google Takvim'e eklendi", icon="✅")
                    st.rerun()

        gunun_gorevleri = list_tasks(current_user_id, due_date=secili_gun)
        if not gunun_gorevleri:
            st.markdown(
                "<div class='fd-empty'><span class='fd-empty-icon'>🗒️</span>"
                "Bu gün için henüz görev eklenmedi.</div>",
                unsafe_allow_html=True,
            )

        for task in gunun_gorevleri:
            _gorev_satirini_ciz(task, current_user_id, secili_gun, profil)

        st.markdown("<br>", unsafe_allow_html=True)
        havuzdaki_gorevler = havuzdaki_gorevleri_listele(current_user_id)
        st.subheader(f"📥 Görev Havuzu ({len(havuzdaki_gorevler)} görev)")
        st.caption("Son tarihi olmayan görevler burada bekler; plan oluştururken boş kalan zamana otomatik eklenebilirler.")
        if not havuzdaki_gorevler:
            st.markdown(
                "<div class='fd-empty'><span class='fd-empty-icon'>📥</span>"
                "Havuzda henüz görev yok.</div>",
                unsafe_allow_html=True,
            )
        for task in havuzdaki_gorevler:
            _gorev_satirini_ciz(task, current_user_id, secili_gun, profil)

        aktif_gorevler = list_tasks(current_user_id, include_done=False, due_date=secili_gun)
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
        havuzdan_doldur = st.checkbox(
            "📥 Havuzdan otomatik doldur", value=True, key="havuzdan_doldur",
            help="İşaretliyse, plan oluşturulurken boş kalan zamana havuzdaki görevlerden uygun olanlar otomatik eklenir.",
        )
        gorevler_plan_icin = aktif_gorevler + havuzdaki_gorevler if havuzdan_doldur else aktif_gorevler

        pcol1, pcol2 = st.columns(2)
        if pcol1.button("🚀 Planı Oluştur", type="primary", width="stretch"):
            if not aktif_gorevler:
                st.warning("Plan oluşturmak için en az bir görev ekleyin.")
            else:
                with st.spinner("Plan oluşturuluyor..."):
                    planning_service.plan_olustur(
                        current_user_id, secili_gun, gorevler_plan_icin, st.session_state["uygun_olmayan_bloklar"], profil,
                        enerji_seviyesi=enerji_service.get_enerji_seviyesi(current_user_id, secili_gun),
                    )
                st.session_state["alternatif_planlar"] = None
                st.success("Plan oluşturuldu! 'AI Planı' sekmesinden görüntüleyebilirsin.")

        if pcol2.button("🔀 Alternatif Planları Karşılaştır", width="stretch"):
            if not aktif_gorevler:
                st.warning("Plan oluşturmak için en az bir görev ekleyin.")
            else:
                with st.spinner("Alternatif planlar hesaplanıyor..."):
                    st.session_state["alternatif_planlar"] = planning_service.alternatif_planlari_uret(
                        gorevler_plan_icin, st.session_state["uygun_olmayan_bloklar"], profil,
                        enerji_seviyesi=enerji_service.get_enerji_seviyesi(current_user_id, secili_gun),
                    )

        alternatif_planlar = st.session_state.get("alternatif_planlar")
        if alternatif_planlar:
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("🔀 Alternatif Planlar")
            acol1, acol2, acol3 = st.columns(3)
            for strateji_col, strateji in zip((acol1, acol2, acol3), planning_service.STRATEJILER):
                hesap = alternatif_planlar[strateji]
                havuzdan_dolan = sum(1 for d in hesap["dilimler"] if d["havuzdan"])
                havuzdan_satiri = (
                    f"<span style='color:#898781;'>Havuzdan Dolan: {havuzdan_dolan} görev</span><br>"
                    if havuzdan_doldur else ""
                )
                with strateji_col:
                    st.markdown(
                        f"<div class='fd-info-card'>"
                        f"<strong>{planning_service.STRATEJI_ETIKETLERI[strateji]}</strong><br>"
                        f"<span style='color:#898781;'>Toplam İş: {hesap['toplam_is_dakika']} dk</span><br>"
                        f"<span style='color:#898781;'>Boş Zaman: {hesap['bos_zaman_dakika']} dk</span><br>"
                        f"<span style='color:#898781;'>Yerleşemeyen: {hesap['yerlesemeyen']} görev</span><br>"
                        f"{havuzdan_satiri}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("Bu Planı Kullan", key=f"alt_plan_sec_{strateji}", width="stretch"):
                        with st.spinner("Plan kaydediliyor..."):
                            planning_service.plan_olustur(
                                current_user_id, secili_gun, gorevler_plan_icin,
                                st.session_state["uygun_olmayan_bloklar"], profil,
                                enerji_seviyesi=enerji_service.get_enerji_seviyesi(current_user_id, secili_gun),
                                strateji=strateji,
                            )
                        st.session_state["alternatif_planlar"] = None
                        st.success("Plan kaydedildi! 'AI Planı' sekmesinden görüntüleyebilirsin.")
                        st.rerun()

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
    kayit = planning_service.son_plan(current_user_id, gosterilecek_gun)

    if kayit is None:
        st.markdown(
            "<div class='fd-empty'><span class='fd-empty-icon'>🗓️</span>"
            "Bu gün için henüz bir plan oluşturulmadı — 'Plan Oluştur' sekmesinden oluşturabilirsin.</div>",
            unsafe_allow_html=True,
        )
    else:
        aktif_gorev_sayisi = len(list_tasks(current_user_id, include_done=False, due_date=kayit.gun))
        yerlesemeyen_sayisi = max(aktif_gorev_sayisi - len(kayit.dilimler), 0)
        if not kayit.dilimler:
            rozet, rozet_renk, rozet_ton = "Planlanamadı", RENK_KRITIK, RENK_KRITIK_TON
        elif yerlesemeyen_sayisi:
            rozet, rozet_renk, rozet_ton = "Kısmen Planlandı", RENK_UYARI, RENK_UYARI_TON
        else:
            rozet, rozet_renk, rozet_ton = "Tamamen Planlandı ✓", RENK_IYI, RENK_IYI_TON

        gun_adi = GUNLER[kayit.gun.weekday()]
        gun_metni = f"{gun_adi}, {kayit.gun.day} {AYLAR[kayit.gun.month - 1]} {kayit.gun.year}"
        enerji_rozeti = (
            f" <span class='fd-badge' style='background:{RENK_MAVI_TON}; color:{RENK_MAVI};'>"
            f"{ENERJI_ETIKETLERI[kayit.enerji_seviyesi]} enerji</span>"
            if kayit.enerji_seviyesi else ""
        )
        strateji_rozeti = (
            f" <span class='fd-badge' style='background:{RENK_MAVI_TON}; color:{RENK_MAVI};'>"
            f"{planning_service.STRATEJI_ETIKETLERI[kayit.strateji]}</span>"
            if kayit.strateji and kayit.strateji != "oncelik_agirlikli" else ""
        )
        st.markdown(
            f"<div class='fd-info-card'>"
            f"<span style='color:#898781;'>{gun_metni}</span><br>"
            f"<strong style='font-size:1.2rem;'>Günlük Plan Hazır</strong><br>"
            f"<span class='fd-badge' style='background:{rozet_ton}; color:{rozet_renk};'>{rozet}</span>"
            f"{enerji_rozeti}{strateji_rozeti}</div>",
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

        if kayit.dilimler:
            st.subheader("🕐 Gün Akışı")
            profil_cizelge = profil_service.get_or_create(current_user_id)
            gun_baslangic_dk = _gun_dakikasi(GUN_BASLANGIC)
            gun_bitis_dk = _gun_dakikasi(GUN_BITIS)
            gorev_oncelikleri = {t.id: t.priority for t in list_tasks(current_user_id, due_date=kayit.gun)}

            parcalar = [
                f"<div class='fd-zaman-etiket' style='top:{s - gun_baslangic_dk - 6}px;'>{s // 60:02d}:00</div>"
                for s in range(gun_baslangic_dk, gun_bitis_dk + 1, 60)
            ]
            for uyku_b, uyku_e in _uyku_bloklari_gun_icinde(profil_cizelge.uyku_baslangic, profil_cizelge.uyku_bitis):
                parcalar.append(
                    f"<div class='fd-zaman-uyku' style='top:{uyku_b - gun_baslangic_dk}px; "
                    f"height:{uyku_e - uyku_b}px;'>😴 Uyku</div>"
                )
            for dilim in kayit.dilimler:
                d_baslangic_dk = _saat_metni_dakikaya(dilim["start"])
                oncelik = gorev_oncelikleri.get(dilim.get("task_id"), 2)
                parcalar.append(
                    f"<div class='fd-zaman-blok' style='top:{d_baslangic_dk - gun_baslangic_dk}px; "
                    f"height:{max(dilim['duration_minutes'] - 2, 16)}px; "
                    f"background:{ONCELIK_TON[oncelik]}; color:{ONCELIK_RENK[oncelik]}; "
                    f"border-left-color:{ONCELIK_RENK[oncelik]};'>"
                    f"{dilim['start']}–{dilim['end']} · {dilim['title']}</div>"
                )
            if kayit.gun == date.today():
                simdi_dk = _gun_dakikasi(datetime.now().time())
                if gun_baslangic_dk <= simdi_dk <= gun_bitis_dk:
                    parcalar.append(
                        f"<div class='fd-zaman-simdi' style='top:{simdi_dk - gun_baslangic_dk}px;'></div>"
                    )

            st.markdown(
                f"<div class='fd-zaman-cizelgesi' style='height:{gun_bitis_dk - gun_baslangic_dk}px;'>"
                + "".join(parcalar) + "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("📊 Önerilen Sıralama")
        if not kayit.dilimler:
            st.markdown(
                "<div class='fd-empty'><span class='fd-empty-icon'>🧩</span>"
                "Hiçbir görev yerleştirilemedi.</div>",
                unsafe_allow_html=True,
            )
        for dilim in kayit.dilimler:
            havuzdan_rozeti = (
                f" <span class='fd-badge' style='background:{RENK_MAVI_TON}; color:{RENK_MAVI};'>📥 Havuzdan</span>"
                if dilim.get("havuzdan") else ""
            )
            st.markdown(
                f"<div class='fd-dilim-card'>"
                f"<span style='color:#898781; font-size:0.85rem;'>{dilim['start']} — {dilim['end']}</span><br>"
                f"<strong>📝 {dilim['title']} ({dilim['duration_minutes']} dk)</strong>{havuzdan_rozeti}<br>"
                f"<span style='color:{RENK_MAVI}; font-style:italic; font-size:0.9rem;'>"
                f"💬 {dilim['gerekce']}</span></div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            f"<div class='fd-oneri-kutu'>💡 <strong>Yapay Zeka Önerisi</strong><br>{kayit.genel_tavsiye}</div>",
            unsafe_allow_html=True,
        )

        if kayit.gun <= date.today():
            degerlendirme = degerlendirme_service.gun_sonu_degerlendirmesi_uret(current_user_id, kayit.gun)
            if degerlendirme:
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("🌙 Gün Sonu Değerlendirmesi")
                dcol1, dcol2 = st.columns(2)
                dcol1.markdown(
                    f"<div class='fd-info-card' style='text-align:center;'>"
                    f"<span style='color:#898781;'>Tamamlama Oranı</span><br>"
                    f"<strong style='font-size:1.4rem;'>%{degerlendirme['tamamlama_orani']}</strong></div>",
                    unsafe_allow_html=True,
                )
                dcol2.markdown(
                    f"<div class='fd-info-card' style='text-align:center;'>"
                    f"<span style='color:#898781;'>Tamamlanan</span><br>"
                    f"<strong style='font-size:1.4rem;'>{degerlendirme['tamamlanan_sayisi']}/"
                    f"{degerlendirme['planlanan_sayisi']}</strong></div>",
                    unsafe_allow_html=True,
                )
                if degerlendirme["tamamlanmayanlar"]:
                    st.caption("Tamamlanmayanlar: " + ", ".join(degerlendirme["tamamlanmayanlar"]))
                st.markdown(
                    f"<div class='fd-oneri-kutu'>🌙 <strong>Gün Sonu Yorumu</strong><br>{degerlendirme['yorum']}</div>",
                    unsafe_allow_html=True,
                )

        if st.button("← Geri Dön & Değiştir"):
            st.toast("Değişiklik için 'Plan Oluştur' sekmesine geç.", icon="↩️")

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
with tab_rapor:
    st.markdown("<div class='fd-header'>📊 Verim &amp; Erteleme Raporu</div>", unsafe_allow_html=True)
    st.markdown("<div class='fd-card'>", unsafe_allow_html=True)

    rapor_profil = profil_service.get_or_create(current_user_id)
    rapor = report_service.haftalik_rapor(current_user_id, profil=rapor_profil)
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
        f"<div class='fd-stat-tile' style='background:{RENK_IYI_TON}; color:{RENK_IYI};'>"
        f"<span class='deger'>%{rapor['verimlilik_orani']}</span>"
        f"<span class='etiket'>Verimlilik Oranı</span></div>",
        unsafe_allow_html=True,
    )
    tcol2.markdown(
        f"<div class='fd-stat-tile' style='background:{RENK_UYARI_TON}; color:{RENK_UYARI};'>"
        f"<span class='deger'>%{rapor['erteleme_orani']}</span>"
        f"<span class='etiket'>Erteleme Oranı</span></div>",
        unsafe_allow_html=True,
    )
    tcol3, tcol4 = st.columns(2)
    tcol3.markdown(
        f"<div class='fd-stat-tile' style='background:{RENK_MAVI_TON}; color:{RENK_MAVI};'>"
        f"<span class='deger'>{rapor['tamamlanan_sayisi']}</span>"
        f"<span class='etiket'>Tamamlanan Görev</span></div>",
        unsafe_allow_html=True,
    )
    tcol4.markdown(
        f"<div class='fd-stat-tile' style='background:{RENK_KRITIK_TON}; color:{RENK_KRITIK};'>"
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
        st.markdown(
            "<div class='fd-empty'><span class='fd-empty-icon'>🎉</span>"
            "Henüz ertelenen görev yok.</div>",
            unsafe_allow_html=True,
        )
    for satir in rapor["en_cok_ertelenenler"]:
        st.markdown(f"<div class='fd-gorev-row'>{satir}</div>", unsafe_allow_html=True)

    if rapor["erteleme_onerileri"]:
        st.subheader("💡 Erteleme Önerileri")
        for oneri in rapor["erteleme_onerileri"]:
            st.warning(oneri)

    verimli_saat_onerisi = report_service.verimli_saat_onerisi(current_user_id, profil=rapor_profil)
    if verimli_saat_onerisi:
        st.info(
            f"Verilerine göre en verimli saatlerin "
            f"{verimli_saat_onerisi['baslangic'].strftime('%H:%M')}–{verimli_saat_onerisi['bitis'].strftime('%H:%M')} "
            f"arası görünüyor (%{verimli_saat_onerisi['yuzde']} tamamlama). "
            "Profildeki 'En Verimli Saatler'i buna göre güncellemek ister misin?"
        )
        if st.button("Profili Güncelle", key="profili_verimli_saate_gore_guncelle"):
            profil_service.save(
                current_user_id,
                rapor_profil.ad_soyad,
                rapor_profil.e_posta,
                verimli_saat_onerisi["baslangic"],
                verimli_saat_onerisi["bitis"],
                rapor_profil.uyku_baslangic,
                rapor_profil.uyku_bitis,
                rapor_profil.gunluk_hedef,
                rapor_profil.buffer_dakika,
            )
            st.session_state["profil_widget_surumu"] = st.session_state.get("profil_widget_surumu", 0) + 1
            st.success("Profil güncellendi.")
            st.rerun()

    rutin_performansi = report_service.rutin_performans_ozeti(current_user_id)
    if rutin_performansi:
        st.subheader("🔁 Rutin Performansı")
        for ozet in rutin_performansi:
            rpc1, rpc2 = st.columns([1, 5])
            rpc1.markdown(f"<span style='color:#52514e;'>{_guvenli_metin(ozet['baslik'])}</span>", unsafe_allow_html=True)
            rpc2.markdown(
                f"<div class='fd-bucket-track'><div class='fd-bucket-fill' style='width:{ozet['oran']}%;'></div></div>"
                f"<span style='color:#52514e; font-size:0.8rem;'>%{ozet['oran']} "
                f"({ozet['tamamlanan']}/{ozet['toplam']})</span>",
                unsafe_allow_html=True,
            )

    st.subheader("📈 Haftalık Trend")
    for nokta in report_service.haftalik_trend(current_user_id):
        tc1, tc2 = st.columns([1, 5])
        tc1.markdown(
            f"<span style='color:#52514e;'>{nokta['hafta_bitis'].day} {AYLAR[nokta['hafta_bitis'].month - 1]}</span>",
            unsafe_allow_html=True,
        )
        tc2.markdown(
            f"<div class='fd-bucket-track'><div class='fd-bucket-fill' "
            f"style='width:{nokta['verimlilik_orani']}%;'></div></div>"
            f"<span style='color:#52514e; font-size:0.8rem;'>%{nokta['verimlilik_orani']}</span>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div class='fd-analiz-kutu'>💡 <strong>Yapay Zeka Analizi</strong><br>{rapor['analiz_metni']}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Admin — sadece is_admin=True kullanıcılara görünür
# ---------------------------------------------------------------------------
if tab_admin is not None:
    with tab_admin:
        st.markdown("<div class='fd-header'>🛠️ Admin</div>", unsafe_allow_html=True)
        st.markdown("<div class='fd-card'>", unsafe_allow_html=True)

        kullanicilar = user_service.list_users()

        st.subheader("👥 Kullanıcılar")
        st.dataframe(
            [
                {
                    "Kullanıcı Adı": u.username,
                    "Admin mi": "Evet" if u.is_admin else "Hayır",
                    "Kayıt Tarihi": u.created_at.strftime("%d.%m.%Y"),
                    "Görev Sayısı": len(list_tasks(u.id)),
                }
                for u in kullanicilar
            ],
            width="stretch",
            hide_index=True,
        )

        st.subheader("🔍 Kullanıcı Detayı ve Yönetimi")
        secilen_ad = st.selectbox(
            "Kullanıcı seç", options=[u.username for u in kullanicilar], key="admin_secili_kullanici"
        )
        secilen = next(u for u in kullanicilar if u.username == secilen_ad)

        detay_gorevler = list_tasks(secilen.id)
        st.caption(f"📋 {len(detay_gorevler)} görev")
        if detay_gorevler:
            st.dataframe(
                [
                    {
                        "Başlık": t.title,
                        "Öncelik": ONCELIK_ETIKET[t.priority],
                        "Bitti mi": "Evet" if t.done else "Hayır",
                        "Son Tarih": t.due_date,
                        "Süre (dk)": t.duration_minutes,
                        "Erteleme": t.postponement_count,
                    }
                    for t in detay_gorevler
                ],
                width="stretch",
                hide_index=True,
            )

        detay_planlar = planning_service.kullanicinin_planlari(secilen.id)
        st.caption(f"🗓️ {len(detay_planlar)} plan kaydı")
        if detay_planlar:
            st.dataframe(
                [
                    {
                        "Gün": p.gun,
                        "Oluşturulma": p.created_at.strftime("%d.%m.%Y %H:%M"),
                        "Dilim Sayısı": len(p.dilimler),
                        "Toplam İş (dk)": p.toplam_is_dakika,
                    }
                    for p in detay_planlar
                ],
                width="stretch",
                hide_index=True,
            )

        detay_etkinlikler = sync_service.list_events(secilen.id)
        st.caption(f"📅 {len(detay_etkinlikler)} takvim etkinliği")
        if detay_etkinlikler:
            st.dataframe(
                [{"Başlık": e.title, "Başlangıç": e.start, "Bitiş": e.end} for e in detay_etkinlikler],
                width="stretch",
                hide_index=True,
            )

        st.markdown("**⚙️ Yönetim**")
        mcol1, mcol2 = st.columns(2)
        if mcol1.button(
            "Admin yetkisini kaldır" if secilen.is_admin else "Admin yap",
            key="admin_toggle",
            disabled=secilen.id == current_user_id,
            help="Kendi admin yetkini kaldıramazsın" if secilen.id == current_user_id else None,
        ):
            try:
                user_service.set_admin(secilen.id, not secilen.is_admin)
                st.toast(f"{secilen.username} artık {'admin değil' if secilen.is_admin else 'admin'}", icon="✅")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

        with st.form("admin_sifre_sifirla_formu"):
            yeni_sifre = st.text_input("Yeni parola", type="password")
            if st.form_submit_button("🔑 Parolayı Sıfırla"):
                try:
                    user_service.sifre_sifirla(secilen.id, yeni_sifre)
                    st.success(f"{secilen.username} için parola sıfırlandı.")
                except ValueError as e:
                    st.error(str(e))

        st.markdown("**🗑️ Hesabı Sil**")
        onay = st.checkbox(
            f"{secilen.username} hesabını ve TÜM verisini kalıcı olarak silmeyi onaylıyorum",
            key="admin_silme_onay",
        )
        if st.button("Hesabı Kalıcı Olarak Sil", disabled=not onay, key="admin_hesap_sil"):
            if secilen.id == current_user_id:
                st.error("Kendi hesabını silemezsin.")
            else:
                try:
                    user_service.delete_user(secilen.id)
                    st.success(f"{secilen.username} silindi.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

        st.markdown("</div>", unsafe_allow_html=True)
