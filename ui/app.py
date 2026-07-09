from datetime import date

import streamlit as st

from core.services.task_service import (
    complete_task,
    create_task,
    delete_task,
    list_tasks,
    update_task,
)

st.set_page_config(page_title="Planlayıcı", layout="wide")
st.title("Planlayıcı — v0.3")

ONCELIK_ETIKET = {3: "Yüksek", 2: "Orta", 1: "Düşük"}

# --- Yeni görev formu: kenar çubuğuna taşındı ---
with st.sidebar:
    st.header("Yeni görev")
    with st.form("yeni_gorev", clear_on_submit=True):
        f_title = st.text_input("Başlık")
        f_desc = st.text_area("Açıklama", height=100)
        f_priority = st.select_slider("Öncelik", options=[1, 2, 3], value=1,
                                      format_func=lambda p: ONCELIK_ETIKET[p])
        f_due = st.date_input("Son tarih", value=None)
        if st.form_submit_button("Ekle", use_container_width=True):
            try:
                create_task(f_title, f_desc, f_priority, f_due)
                st.success("Görev eklendi")
            except ValueError as e:
                st.error(str(e))


def gorev_karti(task) -> None:
    """Tek bir görevi açılır panel olarak çizer."""
    parcalar = [ONCELIK_ETIKET[task.priority]]
    if task.due_date:
        gecikti = " · GECİKTİ" if (not task.done and task.due_date < date.today()) else ""
        parcalar.append(f"{task.due_date:%d.%m.%Y}{gecikti}")
    baslik = f"{task.title}  —  {' · '.join(parcalar)}"

    with st.expander(baslik):
        with st.form(f"duzenle_{task.id}"):
            e_title = st.text_input("Başlık", value=task.title)
            e_desc = st.text_area("Açıklama", value=task.description, height=100)
            e_priority = st.select_slider("Öncelik", options=[1, 2, 3],
                                          value=task.priority,
                                          format_func=lambda p: ONCELIK_ETIKET[p])
            e_due = st.date_input("Son tarih", value=task.due_date)

            col1, col2, col3 = st.columns(3)
            kaydet = col1.form_submit_button("Kaydet", use_container_width=True)
            bitir = col2.form_submit_button("Bitir", use_container_width=True,
                                            disabled=task.done)
            sil = col3.form_submit_button("Sil", type="primary",
                                          use_container_width=True)
        if kaydet:
            try:
                update_task(task.id, e_title, e_desc, e_priority, e_due)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        if bitir:
            complete_task(task.id)
            st.rerun()
        if sil:
            delete_task(task.id)
            st.rerun()


# --- Görev listesi: sekmeli görünüm ---
tab_aktif, tab_biten = st.tabs(["Aktif görevler", "Tamamlananlar"])

with tab_aktif:
    aktifler = list_tasks(include_done=False)
    if not aktifler:
        st.info("Aktif görev yok — kenar çubuğundan ekleyebilirsin.")
    for task in aktifler:
        gorev_karti(task)

with tab_biten:
    bitenler = list_tasks(only_done=True)
    if not bitenler:
        st.caption("Henüz tamamlanan görev yok.")
    for task in bitenler:
        gorev_karti(task)