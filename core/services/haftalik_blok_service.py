"""Haftalık tekrar eden, kalıcı sabit kapalı/serbest zaman blokları.

Bir blok tek bir haftanın günü için geçerlidir (bkz. HaftalikBlok modeli).
Sadece ekle/listele/sil vardır — düzenlemek isteyen kullanıcı silip yeniden
ekler (mevcut ad-hoc "Uygun Olmayan Saatler" listesindeki desenle tutarlı).
"""

from datetime import time

from core.database import SessionLocal
from core.models import HaftalikBlok

GECERLI_TURLER = ("sabit_kapali", "serbest")
GECERLI_GUNLER = range(7)


def create_blok(
    user_id: int, tur: str, gun: int, baslangic: time, bitis: time, etiket: str = ""
) -> HaftalikBlok:
    """Yeni haftalık bloğu doğrular ve kaydeder."""
    if tur not in GECERLI_TURLER:
        raise ValueError("Tür 'sabit_kapali' veya 'serbest' olmalı")
    if gun not in GECERLI_GUNLER:
        raise ValueError("Geçersiz gün değeri")
    if bitis <= baslangic:
        raise ValueError("Bitiş, başlangıçtan sonra olmalı")

    with SessionLocal() as session:
        blok = HaftalikBlok(
            user_id=user_id, tur=tur, gun=gun, baslangic=baslangic, bitis=bitis, etiket=etiket.strip(),
        )
        session.add(blok)
        session.commit()
        session.refresh(blok)
        return blok


def list_bloklar(user_id: int, gun: int | None = None) -> list[HaftalikBlok]:
    """Kullanıcının bloklarını döner; `gun` verilirse sadece o güne ait olanları."""
    with SessionLocal() as session:
        query = session.query(HaftalikBlok).filter(HaftalikBlok.user_id == user_id)
        if gun is not None:
            query = query.filter(HaftalikBlok.gun == gun)
        return list(query.order_by(HaftalikBlok.gun, HaftalikBlok.baslangic))


def delete_blok(user_id: int, blok_id: int) -> None:
    """Bloğu kalıcı olarak siler."""
    with SessionLocal() as session:
        blok = (
            session.query(HaftalikBlok)
            .filter(HaftalikBlok.id == blok_id, HaftalikBlok.user_id == user_id)
            .one_or_none()
        )
        if blok is None:
            raise ValueError(f"{blok_id} numaralı blok bulunamadı.")
        session.delete(blok)
        session.commit()
