import streamlit as st

from core.database import init_db
from core.services.task_service import create_task, complete_task, list_tasks, delete_task

init_db()

st.title("Planlayıcı - v0.2")

with st.form("yeni_gorev", clear_on_submit=True):
    title = st.text_input("Görev başlığı")
    description = st.text_area("Açıklama", height=80)
    priority = st.select_slider("Öncelik", options=[1, 2, 3], value=1)
    due_date = st.date_input("Son tarih", value=None)
    if st.form_submit_button("Ekle"):
        try:
            task = create_task(title, description, priority, due_date)
            st.success(f"Oluşturuldu: {task.title}")
        except ValueError as e:
            st.error(str(e))

st.divider()
st.subheader("Görevler")

for task in list_tasks(include_done=False):
    col_text, col_btn = st.columns([5, 1])
    etiket = {3: "Yüksek", 2: "Orta", 1: "Düşük"}[task.priority]
    col_text.write(f"{task.title} . {etiket} öncelik")
    if col_btn.button("Bitir", key=f"done_{task.id}"):
        complete_task(task.id)
        st.rerun()