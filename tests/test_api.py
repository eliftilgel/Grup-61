"""api/main.py için duman (smoke) testleri — uygulamanın en azından ayağa kalktığını doğrular."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_bos_liste_donuyor(test_db, test_user_id):
    yanit = client.get("/tasks", params={"user_id": test_user_id})

    assert yanit.status_code == 200
    assert yanit.json() == []


def test_gorev_olusturma_ve_listeleme(test_db, test_user_id):
    olusturma = client.post(
        "/tasks", params={"user_id": test_user_id}, json={"title": "Rapor yaz", "priority": 3}
    )
    assert olusturma.status_code == 201
    gorev = olusturma.json()
    assert gorev["title"] == "Rapor yaz"
    assert gorev["priority"] == 3
    assert gorev["done"] is False

    listeleme = client.get("/tasks", params={"user_id": test_user_id})
    assert listeleme.status_code == 200
    assert len(listeleme.json()) == 1


def test_bos_baslikla_olusturma_422_doner(test_db, test_user_id):
    yanit = client.post("/tasks", params={"user_id": test_user_id}, json={"title": "   "})

    assert yanit.status_code == 422


def test_gorev_tamamlama_ve_silme(test_db, test_user_id):
    gorev = client.post(
        "/tasks", params={"user_id": test_user_id}, json={"title": "Alışveriş"}
    ).json()

    tamamlama = client.patch(f"/tasks/{gorev['id']}/complete", params={"user_id": test_user_id})
    assert tamamlama.status_code == 200
    assert tamamlama.json()["done"] is True

    silme = client.delete(f"/tasks/{gorev['id']}", params={"user_id": test_user_id})
    assert silme.status_code == 204


def test_olmayan_gorevi_tamamlama_404_doner(test_db, test_user_id):
    yanit = client.patch("/tasks/999999/complete", params={"user_id": test_user_id})

    assert yanit.status_code == 404


def test_baska_kullanicinin_gorevine_erisim_404_doner(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_api", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    gorev = client.post(
        "/tasks", params={"user_id": diger_id}, json={"title": "Diğerinin görevi"}
    ).json()

    yanit = client.patch(f"/tasks/{gorev['id']}/complete", params={"user_id": test_user_id})
    assert yanit.status_code == 404
