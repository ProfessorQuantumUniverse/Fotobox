"""Render real screenshots of every Fotobox screen for the README.

Usage:
    # 1. start the server with the demo photo dir
    FOTOBOX_PORT=5050 FOTOBOX_SHARE_MODE=hotspot \
        FOTOBOX_PHOTO_DIR=/tmp/fotobox-shots python -m server.app &
    # 2. drop a demo photo into /tmp/fotobox-shots/foto_demo.jpg
    # 3. run this script (needs: pip install playwright, system Chrome)
    python docs/make_screenshots.py

Each shot loads the real running page and drives the SSE-driven screens via
page.evaluate – no production/debug code is added to the app itself.
"""
import os
import sys
from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ.setdefault("FOTOBOX_PHOTO_DIR", "/tmp/fotobox-shots")
from server.app import _make_qr_data_uri, _make_wifi_qr  # noqa: E402

OUT = os.path.join(REPO, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)
URL = "http://127.0.0.1:%s/" % os.environ.get("FOTOBOX_PORT", "5050")

wifi_qr = _make_wifi_qr("Fotobox-4821", "k7Rm!q2Xz9aP")
dl_qr = _make_qr_data_uri("http://10.42.0.1:5050/download")
nc_qr = _make_qr_data_uri("https://cloud.example.org/s/aB9xK2mQ7")

# JS snippets per shot. Each gets a fresh page load.
ACTIVATE = """(args) => {
  const {screen} = args;
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(screen).classList.add('active');
  document.body.style.cursor = 'none';
}"""

SHOTS = []

def shot(name, js, w=900, h=1350, wait=350):
    SHOTS.append((name, js, w, h, wait))

shot("01-idle", "(a)=>{}")

shot("02-countdown", """(a)=>{
  const n=document.getElementById('countdown-number'); n.textContent='3';
  const d=document.getElementById('countdown-dots'); d.innerHTML='';
  for(let i=0;i<8;i++){const e=document.createElement('div');e.className='dot'+(i>=3?' off':'');d.appendChild(e);}
}""")

shot("03-review", """(a)=>{
  document.getElementById('review-photo').src='/photos/preview/foto_demo.jpg';
  const b=document.getElementById('review-timer-bar'); b.style.transitionDuration='0s'; b.style.transform='scaleX(0.55)';
}""")

shot("04-qr-hotspot", f"""(a)=>{{
  document.getElementById('box-wifi').style.display='flex';
  document.getElementById('qr-code-img').src='{wifi_qr}';
  document.getElementById('qr-download-img').src='{dl_qr}';
  document.getElementById('qr-ssid').textContent='Fotobox-4821';
  document.getElementById('qr-password').textContent='k7Rm!q2Xz9aP';
  document.getElementById('qr-url').textContent='http://10.42.0.1:5050/download';
}}""", h=1500)

shot("05-qr-nextcloud", f"""(a)=>{{
  document.getElementById('box-wifi').style.display='none';
  document.getElementById('step-number-download').textContent='1';
  document.getElementById('instruction-download').textContent='Code mit der Kamera-App scannen';
  document.getElementById('qr-download-img').src='{nc_qr}';
  document.getElementById('qr-url').textContent='';
}}""")

shot("06-toast-update", """(a)=>{
  const t=document.getElementById('toast'); t.classList.remove('hide-progress'); t.classList.add('show');
  document.getElementById('toast-icon').innerHTML='<div class="toast-spinner"></div>';
  document.getElementById('toast-title').textContent='Update läuft';
  document.getElementById('toast-message').textContent='Lade Update herunter …';
  document.getElementById('toast-percent').textContent='67%';
  document.getElementById('toast-progress-bar').style.width='67%';
}""", h=900)

shot("07-toast-disconnected", """(a)=>{
  const t=document.getElementById('toast'); t.classList.add('toast-error'); t.classList.add('hide-progress'); t.classList.add('show');
  document.getElementById('toast-icon').innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 7l3-3a5 5 0 0 1 7 7"/><path d="M8 17l-3 3"/><path d="M3 3l18 18"/></svg>';
  document.getElementById('toast-title').textContent='LAN getrennt';
  document.getElementById('toast-message').textContent='Vorherige Version bleibt aktiv';
}""", h=900)

shot("08-error", """(a)=>{
  document.getElementById('error-message').textContent='Kamera nicht gefunden – bitte USB prüfen';
}""", h=900)

screen_for = {
  "01-idle":"screen-idle","02-countdown":"screen-countdown","03-review":"screen-review",
  "04-qr-hotspot":"screen-qr","05-qr-nextcloud":"screen-qr","06-toast-update":"screen-idle",
  "07-toast-disconnected":"screen-idle","08-error":"screen-error",
}

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    for name, js, w, h, wait in SHOTS:
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        page.goto(URL, wait_until="load")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(150)
        page.evaluate(ACTIVATE, {"screen": screen_for[name]})
        page.evaluate(js, {})
        page.wait_for_timeout(wait)
        page.screenshot(path=f"{OUT}/{name}.png")
        print("shot", name)
        page.close()

    # Guest download gallery on a phone viewport
    page = browser.new_page(viewport={"width": 414, "height": 896}, device_scale_factor=2)
    page.goto(URL + "download", wait_until="load")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(300)
    page.screenshot(path=f"{OUT}/09-download-mobile.png", full_page=True)
    print("shot 09-download-mobile")
    page.close()
    browser.close()
print("DONE")
