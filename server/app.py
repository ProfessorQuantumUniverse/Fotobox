# ... OBEN in die Imports von app.py hinzufügen:
from server.config import AP_IP, HOST, PHOTO_DIR, PORT, REVIEW_SECONDS, SHARE_MODE
from server.nextcloud_client import process_nextcloud_upload

# ... Die session_finish Route in app.py ersetzen:
@app.route("/session/finish", methods=["POST"])
def session_finish():
    """Finalise the current session, start an AP/Nextcloud upload, and return QR code data."""
    with _session_lock:
        photos = list(_session_photos)
        _session_photos.clear()
        _last_finished_session_photos.clear()
        _last_finished_session_photos.extend(photos)

    if SHARE_MODE == "nextcloud":
        # NEXTCLOUD MODUS
        share_url = process_nextcloud_upload(photos)
        
        # Falls Nextcloud nicht erreichbar war, Fallback auf Hotspot
        if not share_url:
            logger.error("Nextcloud Share URL konnte nicht generiert werden!")
            return jsonify({"error": "Cloud upload failed"}), 500

        download_qr_data_uri = _make_text_qr(share_url)
        logger.info("Session finished: %d photo(s), Nextcloud URL=%s", len(photos), share_url)
        
        return jsonify({
            "share_mode": "nextcloud",
            "photos": photos,
            "download_url": share_url,
            "download_qr": download_qr_data_uri,
        })
        
    else:
        # HOTSPOT MODUS (Altes Verhalten)
        ssid, password = generate_ap_credentials()
        wifi_qr_data_uri = _make_wifi_qr(ssid, password)
        download_url = f"http://{AP_IP}:{PORT}/download"
        download_qr_data_uri = _make_text_qr(download_url)

        # Start the AP in a background thread; non-daemon so shutdown waits for it.
        Thread(target=create_ap, args=(ssid, password)).start()

        logger.info("Session finished: %d photo(s), AP SSID=%s", len(photos), ssid)
        return jsonify({
            "share_mode": "hotspot",
            "photos": photos,
            "ssid": ssid,
            "password": password,
            "download_url": download_url,
            "wifi_qr": wifi_qr_data_uri,
            "download_qr": download_qr_data_uri,
        })
