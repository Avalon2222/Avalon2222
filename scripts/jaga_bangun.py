"""Membangunkan dan menjaga aplikasi Streamlit Community Cloud agar tidak tertidur.

Aplikasi gratis di Streamlit Community Cloud tertidur bila beberapa hari tanpa kunjungan,
dan hanya bangun lewat tombol "Yes, get this app back up!" di browser. Skrip ini membuka
setiap aplikasi dengan browser headless (Playwright), menekan tombol itu bila muncul, lalu
menunggu sampai aplikasi benar-benar menggambar isinya. Dijalankan terjadwal oleh GitHub
Actions (.github/workflows/jaga-bangun.yml); bisa juga dijalankan manual:

    pip install playwright && playwright install chromium
    python scripts/jaga_bangun.py                # semua aplikasi
    python scripts/jaga_bangun.py https://...    # hanya URL yang disebut

Catatan: Streamlit Cloud menampilkan aplikasi di dalam iframe, sehingga pemeriksaan isi
dilakukan di semua frame, bukan hanya halaman utama.
"""

from __future__ import annotations

import sys
import time

from playwright.sync_api import sync_playwright

APLIKASI = [
    "https://dc-impact-dashboard.streamlit.app",
    "https://btc-news-volatility.streamlit.app",
    "https://indonesia-defense-gis.streamlit.app",
    "https://ring-of-fire-pulse.streamlit.app",
    "https://who-owns-the-sky.streamlit.app",
    "https://follow-the-money.streamlit.app",
    "https://btc-whale-watch.streamlit.app",
    "https://roof-vs-paycheck.streamlit.app",
    "https://the-air-we-breathe.streamlit.app",
    "https://burning-archipelago.streamlit.app",
    "https://talk-to-the-data.streamlit.app",
    "https://global-conflict-tracker.streamlit.app",
    "https://who-watches-indonesia.streamlit.app",
    "https://blackout-watch.streamlit.app",
    "https://cut-the-cable.streamlit.app",
]

TEKS_TIDUR = "get this app back up"       # potongan teks tombol pada halaman tidur
TUNGGU_MUAT_DETIK = 90                     # batas menunggu aplikasi menggambar isinya
TUNGGU_BANGUN_DETIK = 180                  # batas menunggu setelah tombol bangun ditekan
SELEKTOR_ISI = '[data-testid="stAppViewContainer"] h1, [data-testid="stMarkdownContainer"]'


def _frames(page):
    """Halaman utama beserta semua iframe (Streamlit Cloud membungkus aplikasi dalam iframe)."""
    return list(page.frames)


def ada_isi(page) -> bool:
    for f in _frames(page):
        try:
            if f.locator(SELEKTOR_ISI).count() > 0:
                return True
        except Exception:
            continue
    return False


def tombol_tidur(page):
    """Locator tombol bangun bila halaman tidur sedang tampil, selain itu None."""
    for f in _frames(page):
        try:
            tombol = f.get_by_role("button", name=TEKS_TIDUR, exact=False)
            if tombol.count() > 0:
                return tombol.first
            if f.get_by_text(TEKS_TIDUR, exact=False).count() > 0:
                return f.get_by_text(TEKS_TIDUR, exact=False).first
        except Exception:
            continue
    return None


def tunggu(page, batas_detik: int) -> str:
    """Menunggu sampai isi tampil ("bangun") atau halaman tidur muncul ("tidur"); "habis" bila lewat batas."""
    mulai = time.time()
    while time.time() - mulai < batas_detik:
        if ada_isi(page):
            return "bangun"
        if tombol_tidur(page) is not None:
            return "tidur"
        time.sleep(2)
    return "habis"


def kunjungi(page, url: str) -> str:
    """Mengunjungi satu aplikasi; mengembalikan status singkat untuk log."""
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    status = tunggu(page, TUNGGU_MUAT_DETIK)
    if status == "bangun":
        return "bangun"
    if status == "habis":
        return "tidak merespons dalam batas waktu"

    tombol_tidur(page).click()
    status = tunggu(page, TUNGGU_BANGUN_DETIK)
    if status == "bangun":
        return "tidur → dibangunkan, isi tampil"
    return "tidur → tombol ditekan, isi belum tampil"


def main(daftar: list[str]) -> int:
    gagal = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        for url in daftar:
            page = context.new_page()
            try:
                status = kunjungi(page, url)
            except Exception as exc:  # satu aplikasi gagal tidak boleh menghentikan yang lain
                status = f"gagal: {type(exc).__name__}: {str(exc)[:120]}"
            if status != "bangun" and "isi tampil" not in status:
                gagal += 1
            print(f"{url:<48} {status}", flush=True)
            page.close()
        browser.close()
    print(f"Selesai: {len(daftar) - gagal}/{len(daftar)} aplikasi bangun.")
    return 0  # tidak menggagalkan job: aplikasi yang lambat akan dicoba lagi pada jadwal berikutnya


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or APLIKASI))
