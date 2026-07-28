"""api/main.py için duman (smoke) testleri — uygulamanın en azından ayağa kalktığını doğrular."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_bos_liste_donuyor(test_db):
    yanit = client.get("/tasks")

    assert yanit.status_code == 200
    assert yanit.json() == []


def test_gorev_olusturma_ve_listeleme(test_db):
    olusturma = client.post("/tasks", json={"title": "Rapor yaz", "priority": 3})
    assert olusturma.status_code == 201
    gorev = olusturma.json()
    assert gorev["title"] == "Rapor yaz"
    assert gorev["priority"] == 3
    assert gorev["done"] is False

    listeleme = client.get("/tasks")
    assert listeleme.status_code == 200
    assert len(listeleme.json()) == 1


def test_bos_baslikla_olusturma_422_doner(test_db):
    yanit = client.post("/tasks", json={"title": "   "})

    assert yanit.status_code == 422


def test_gorev_tamamlama_ve_silme(test_db):
    gorev = client.post("/tasks", json={"title": "Alışveriş"}).json()

    tamamlama = client.patch(f"/tasks/{gorev['id']}/complete")
    assert tamamlama.status_code == 200
    assert tamamlama.json()["done"] is True

    silme = client.delete(f"/tasks/{gorev['id']}")
    assert silme.status_code == 204


def test_olmayan_gorevi_tamamlama_404_doner(test_db):
    yanit = client.patch("/tasks/999999/complete")

    assert yanit.status_code == 404
