---
name: flowday-yeni-alan-servis
description: FlowDay'e yeni bir model alanı veya yeni bir servis eklerken izlenecek adım sırası (migration, conftest fixture, vb.)
---

## Yeni bir servis eklerken
- `tests/conftest.py`'deki `test_db` fixture'ına o servisin `SessionLocal`'ını da eklemeyi unutma — aksi halde testler gerçek `planner.db`'ye yazar.

## Yeni bir Task/Profil/PlanKaydi alanı eklerken sıra
1. `core/models.py`
2. Alembic migration (`alembic revision --autogenerate`, elle doğrula)
3. İlgili servis
4. Gerekiyorsa `tests/conftest.py`
