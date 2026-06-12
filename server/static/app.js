/* Fotobox – Frontend logic (SSE-driven state machine) */

(function () {
  "use strict";

  var COUNTDOWN_SECONDS = 8; // muss zum Arduino-/Trigger-Countdown passen

  // Screen elements
  var screenIdle      = document.getElementById("screen-idle");
  var screenCountdown = document.getElementById("screen-countdown");
  var screenReview    = document.getElementById("screen-review");
  var screenQr        = document.getElementById("screen-qr");
  var screenError     = document.getElementById("screen-error");
  var screenShutdown  = document.getElementById("screen-shutdown");
  var reviewPhoto     = document.getElementById("review-photo");
  var errorMessage    = document.getElementById("error-message");
  var countdownDots   = document.getElementById("countdown-dots");
  var countdownNumber = document.getElementById("countdown-number");
  var reviewTimerBar  = document.getElementById("review-timer-bar");

  // Review buttons
  var btnMorePhotos = document.getElementById("btn-more-photos");
  var btnDone       = document.getElementById("btn-done");

  // QR screen elements
  var qrCodeImg     = document.getElementById("qr-code-img");
  var qrDownloadImg = document.getElementById("qr-download-img");
  var qrSsid        = document.getElementById("qr-ssid");
  var qrPassword    = document.getElementById("qr-password");
  var qrUrl         = document.getElementById("qr-url");
  var btnQrNext     = document.getElementById("btn-qr-next");
  var btnQrBack     = document.getElementById("btn-qr-back");
  var btnQrHome     = document.getElementById("btn-qr-home");

  // Shutdown-Menü
  var btnShutdownCancel  = document.getElementById("btn-shutdown-cancel");
  var btnShutdownConfirm = document.getElementById("btn-shutdown-confirm");

  function showQrPage(id) {
    var pages = document.querySelectorAll(".qr-page");
    for (var i = 0; i < pages.length; i++) {
      pages[i].classList.toggle("active", pages[i].id === id);
    }
    // Auto-Rückkehr zur Homepage NUR auf der letzten Folie (Download). Auf der
    // ersten Folie (WLAN) bleibt der Screen stehen, bis der Gast „Weiter“ tippt.
    if (qrTimeout) { clearTimeout(qrTimeout); qrTimeout = null; }
    if (id === "box-download" && window.QR_TIMEOUT_SECONDS && QR_TIMEOUT_SECONDS > 0) {
      qrTimeout = setTimeout(returnToIdle, QR_TIMEOUT_SECONDS * 1000);
    }
  }

  if (btnQrNext) {
    btnQrNext.addEventListener("click", function () { showQrPage("box-download"); });
  }
  if (btnQrBack) {
    btnQrBack.addEventListener("click", function () { showQrPage("box-wifi"); });
  }
  if (btnQrHome) {
    // Zurück zur Startseite – der Hotspot bleibt an, damit Gäste in Ruhe
    // fertig herunterladen können (er wird bei der nächsten Session erneuert).
    btnQrHome.addEventListener("click", returnToIdle);
  }

  var countdownInterval = null;
  var reviewTimeout = null;
  var qrTimeout = null;
  var captureWatchdog = null;   // Sicherheits-Timeout: hängt die Aufnahme, zurück zur Homepage
  var loaderShownAt = 0;        // Zeitstempel, ab dem die Ladeanimation läuft

  // Dauer, die die Aufnahme maximal brauchen darf, bevor die Box von selbst
  // zur Homepage zurückkehrt (Countdown + großzügige Kamera-Reserve).
  var CAPTURE_TIMEOUT_MS = (COUNTDOWN_SECONDS + 35) * 1000;
  // Mindestzeit, die die Ladeanimation zu sehen ist (sonst „blitzt“ sie nur).
  var MIN_LOADER_MS = 650;

  // Toast elements
  var toast          = document.getElementById("toast");
  var toastIcon      = document.getElementById("toast-icon");
  var toastTitle     = document.getElementById("toast-title");
  var toastMessage   = document.getElementById("toast-message");
  var toastPercent   = document.getElementById("toast-percent");
  var toastProgress  = document.getElementById("toast-progress-bar");
  var toastHideTimer = null;

  var ICONS = {
    link: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>',
    unlink: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 7l3-3a5 5 0 0 1 7 7"/><path d="M8 17l-3 3"/><path d="M3 3l18 18"/><path d="M10 13a5 5 0 0 0 6 .9"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>',
    usb: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21V4"/><path d="M9 7l3-3 3 3"/><circle cx="12" cy="21" r="1"/><path d="M8 14l-2 2v2"/><circle cx="6" cy="19" r="1"/><path d="M16 12l2 2v3"/><rect x="16.5" y="9.5" width="3" height="3"/></svg>',
    cross: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    update: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M4 19h16"/></svg>',
    spinner: '<div class="toast-spinner"></div>'
  };

  // ── Helpers ──────────────────────────────────────────

  function clearTimers() {
    if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
    if (reviewTimeout)     { clearTimeout(reviewTimeout);      reviewTimeout = null; }
    if (qrTimeout)         { clearTimeout(qrTimeout);          qrTimeout = null; }
  }

  function clearCaptureWatchdog() {
    if (captureWatchdog) { clearTimeout(captureWatchdog); captureWatchdog = null; }
  }

  function showScreen(screen) {
    clearTimers();
    [screenIdle, screenCountdown, screenReview, screenQr, screenError, screenShutdown].forEach(function (s) {
      s.classList.remove("active");
    });
    screen.classList.add("active");
  }

  function returnToIdle() {
    clearCaptureWatchdog();
    showScreen(screenIdle);
  }

  // ── Toast ─────────────────────────────────────────────

  // Welche Toast gerade zu sehen ist ("update_offer" macht sie antippbar).
  var toastKind = null;

  function showToast(opts) {
    // opts: { icon, title, message, percent, variant, progress (bool), autohide (ms|0), kind }
    if (toastHideTimer) { clearTimeout(toastHideTimer); toastHideTimer = null; }
    toastKind = opts.kind || null;

    toast.classList.remove("toast-error");
    toast.classList.toggle("toast-clickable", toastKind === "update_offer");
    if (opts.variant === "error") { toast.classList.add("toast-error"); }

    toastIcon.innerHTML = ICONS[opts.icon] || "";
    toastTitle.textContent = opts.title || "";
    toastMessage.textContent = opts.message || "";

    var hasProgress = !!opts.progress;
    toast.classList.toggle("hide-progress", !hasProgress);
    if (hasProgress) {
      var pct = Math.max(0, Math.min(100, opts.percent || 0));
      toastProgress.style.width = pct + "%";
      toastPercent.textContent = pct + "%";
    } else {
      toastPercent.textContent = "";
    }

    toast.classList.add("show");

    if (opts.autohide && opts.autohide > 0) {
      toastHideTimer = setTimeout(hideToast, opts.autohide);
    }
  }

  function updateToastProgress(percent, message) {
    var pct = Math.max(0, Math.min(100, percent || 0));
    toast.classList.remove("hide-progress");
    toastProgress.style.width = pct + "%";
    toastPercent.textContent = pct + "%";
    if (message) { toastMessage.textContent = message; }
    toast.classList.add("show");
  }

  function hideToast() {
    toastKind = null;
    toast.classList.remove("show", "toast-clickable");
  }

  // Die Update-Toast bleibt stehen, bis sie angetippt wird (→ PIN-Eingabe)
  // oder ein Foto gestartet wird – kein Timeout.
  toast.addEventListener("click", function () {
    if (toastKind !== "update_offer") { return; }
    hideToast();
    openPinModal();
  });

  // ── Countdown (Zahl + Punkte) ─────────────────────────
  // Wichtig: erst showScreen() (löscht alte Timer), dann das Intervall setzen.

  function startCountdown() {
    var remaining = COUNTDOWN_SECONDS;

    countdownDots.innerHTML = "";
    for (var i = 0; i < COUNTDOWN_SECONDS; i++) {
      var dot = document.createElement("div");
      dot.className = "dot";
      countdownDots.appendChild(dot);
    }

    function render() {
      countdownNumber.textContent = String(remaining);
      countdownNumber.classList.remove("tick");
      void countdownNumber.offsetWidth;
      countdownNumber.classList.add("tick");

      var dots = countdownDots.children;
      for (var j = 0; j < dots.length; j++) {
        dots[j].classList.toggle("off", j >= remaining);
      }
    }

    render();
    countdownInterval = setInterval(function () {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        countdownNumber.textContent = "";
        return;
      }
      render();
    }, 1000);
  }

  // ── Review-Auto-Reset ─────────────────────────────────

  function startReviewTimer() {
    if (!reviewTimerBar || !window.REVIEW_SECONDS || REVIEW_SECONDS <= 0) { return; }
    reviewTimerBar.classList.remove("running");
    reviewTimerBar.style.transitionDuration = "0s";
    void reviewTimerBar.offsetWidth;
    reviewTimerBar.style.transitionDuration = REVIEW_SECONDS + "s";
    reviewTimerBar.classList.add("running");

    reviewTimeout = setTimeout(function () {
      // Foto bleibt in der Session – die Box geht nur zurück in den Idle-Modus.
      returnToIdle();
    }, REVIEW_SECONDS * 1000);
  }

  // ── Shutdown-Menü (5× schnell den Knopf drücken) ──────
  // Fünf Knopfdrücke in einem Zeitfenster öffnen ein Menü, das einen sauberen
  // Shutdown anbietet. „Mittel-schnell“ → großzügiges Fenster (kein Hetzen).

  var SHUTDOWN_TAPS = 5;
  var SHUTDOWN_WINDOW_MS = 4000;
  var pressTimestamps = [];
  var shutdownActive = false;

  function registerPressBurst() {
    var now = Date.now();
    pressTimestamps.push(now);
    // Nur Drücke innerhalb des Fensters behalten.
    pressTimestamps = pressTimestamps.filter(function (t) { return now - t <= SHUTDOWN_WINDOW_MS; });
    return pressTimestamps.length >= SHUTDOWN_TAPS;
  }

  function openShutdownMenu() {
    shutdownActive = true;
    pressTimestamps = [];
    clearCaptureWatchdog();
    // Alles andere beenden: laufenden Hotspot abbauen (kein Foto, keine Session).
    fetch("/session/stop-ap", { method: "POST" })
      .catch(function (err) { console.error("stop-ap error:", err); });
    showScreen(screenShutdown);
  }

  function closeShutdownMenu() {
    shutdownActive = false;
    returnToIdle();
  }

  if (btnShutdownCancel) {
    btnShutdownCancel.addEventListener("click", closeShutdownMenu);
  }
  if (btnShutdownConfirm) {
    btnShutdownConfirm.addEventListener("click", function () {
      btnShutdownConfirm.disabled = true;
      fetch("/system/shutdown", { method: "POST" })
        .catch(function (err) { console.error("shutdown error:", err); });
    });
  }

  // ── PIN-Eingabe → Update installieren ────────────────
  // Die Update-Toast antippen öffnet dieses Pad. Richtige PIN → das Update
  // läuft (git pull, Abhängigkeiten, Skripte), danach startet die Box neu.

  var pinModal = document.getElementById("pin-modal");
  var pinBox   = document.getElementById("pin-box");
  var pinDots  = document.getElementById("pin-dots");
  var pinPad   = document.getElementById("pin-pad");
  var pinValue = "";
  var pinBusy  = false;

  function renderPinDots() {
    pinDots.innerHTML = "";
    for (var i = 0; i < UPDATE_PIN_LENGTH; i++) {
      var d = document.createElement("div");
      d.className = "pin-dot" + (i < pinValue.length ? " filled" : "");
      pinDots.appendChild(d);
    }
  }

  function openPinModal() {
    pinValue = "";
    pinBusy = false;
    renderPinDots();
    pinModal.classList.add("show");
  }

  function closePinModal() {
    pinValue = "";
    pinModal.classList.remove("show");
  }

  function submitPin() {
    pinBusy = true;
    fetch("/system/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: pinValue })
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, status: res.status, data: data };
        });
      })
      .then(function (r) {
        if (r.ok) {
          closePinModal();
          showToast({
            icon: "spinner", title: "Update läuft",
            message: "Bitte warten – die Box startet gleich neu",
            progress: true, percent: 5, autohide: 0, kind: "update_run"
          });
          return;
        }
        if (r.status === 403) {
          // Falsche PIN: schütteln, leeren, neuer Versuch.
          pinValue = "";
          renderPinDots();
          pinBusy = false;
          pinBox.classList.remove("shake");
          void pinBox.offsetWidth;
          pinBox.classList.add("shake");
          return;
        }
        // z. B. Read-Only-Overlay aktiv (409)
        closePinModal();
        showToast({
          icon: "cross", title: "Update nicht möglich",
          message: (r.data && r.data.error) || "Unbekannter Fehler",
          variant: "error", progress: false, autohide: 8000
        });
      })
      .catch(function () {
        pinBusy = false;
        closePinModal();
        showToast({
          icon: "cross", title: "Update nicht möglich", message: "Verbindungsfehler",
          variant: "error", progress: false, autohide: 6000
        });
      });
  }

  pinPad.addEventListener("click", function (e) {
    var key = e.target && e.target.getAttribute("data-key");
    if (!key || pinBusy) { return; }
    if (key === "cancel") { closePinModal(); return; }
    if (key === "clear")  { pinValue = ""; renderPinDots(); return; }
    if (pinValue.length >= UPDATE_PIN_LENGTH) { return; }
    pinValue += key;
    renderPinDots();
    if (pinValue.length === UPDATE_PIN_LENGTH) { submitPin(); }
  });

  // ── SSE Connection ──────────────────────────────────

  function connectSSE() {
    var source = new EventSource("/events");

    source.onmessage = function (e) {
      var msg;
      try {
        msg = JSON.parse(e.data);
      } catch (_) {
        return;
      }

      switch (msg.event) {
        case "button_pressed":
          // 5× schnell hintereinander → Shutdown-Menü (statt neuer Session).
          if (registerPressBurst()) {
            openShutdownMenu();
            break;
          }
          // Steht das Menü schon offen, ignorieren wir weitere Drücke.
          if (shutdownActive) { break; }
          // Läuft bereits ein Countdown, NICHT neu starten – die schnellen
          // Taps zählen nur für die Burst-Erkennung (Shutdown-Menü) weiter.
          if (screenCountdown.classList.contains("active")) { break; }
          // Der physische Knopf startet sonst IMMER eine neue Session sofort.
          // Auf dem QR-Screen heißt das: alten Hotspot abbauen, dann direkt
          // in den Countdown (die Server-Session wurde bei "Fertig" geleert).
          if (screenQr.classList.contains("active")) {
            fetch("/session/stop-ap", { method: "POST" })
              .catch(function (err) { console.error("stop-ap error:", err); });
          }
          startCountdownScreen();
          break;

        case "countdown_complete":
          if (shutdownActive) { break; }  // Menü offen → keine Aufnahme zeigen
          // Sicherheits-Watchdog: kommt kein Foto/Fehler, zurück zur Homepage.
          clearCaptureWatchdog();
          captureWatchdog = setTimeout(returnToIdle, CAPTURE_TIMEOUT_MS);
          break;

        case "photo_taken":
          if (shutdownActive) { break; }  // Menü offen → Foto verwerfen (Datei ist gesichert)
          clearCaptureWatchdog();
          (function (filename) {
            var loader     = document.getElementById("review-loader");
            var photoFrame = document.getElementById("photo-frame");
            // Zustände zurücksetzen: Loader-Loop sichtbar, Frame versteckt.
            loader.classList.remove("done");
            photoFrame.classList.remove("loaded");
            reviewPhoto.onload = null;
            reviewPhoto.src = "";

            showScreen(screenReview);
            loaderShownAt = Date.now();

            function reveal() {
              // Foto + Rahmen erscheinen gemeinsam, Loader blendet aus –
              // aber erst, wenn die Animation lange genug zu sehen war.
              var wait = Math.max(0, MIN_LOADER_MS - (Date.now() - loaderShownAt));
              setTimeout(function () {
                loader.classList.add("done");
                photoFrame.classList.add("loaded");
                startReviewTimer();
              }, wait);
            }
            reviewPhoto.onload = reveal;
            reviewPhoto.onerror = reveal;
            reviewPhoto.src = "/photos/preview/" + encodeURIComponent(filename);
          }(msg.data.filename));
          break;

        case "error":
          clearCaptureWatchdog();
          if (shutdownActive) { break; }
          errorMessage.textContent = msg.data.message || "Unbekannter Fehler";
          showScreen(screenError);
          setTimeout(returnToIdle, 5000);
          break;

        case "usb_storage":
          // USB-Stick ein-/ausgesteckt: Fotos werden gesichert, solange er steckt.
          if (msg.data.present) {
            showToast({
              icon: "usb",
              title: "USB-Stick erkannt",
              message: "Alle Fotos werden gesichert",
              progress: false,
              autohide: 4000
            });
          } else {
            showToast({
              icon: "unlink",
              title: "USB-Stick entfernt",
              message: "Keine Sicherung mehr",
              variant: "error",
              progress: false,
              autohide: 4000
            });
          }
          break;

        case "update_available":
          // Update nur auf der Startseite anbieten. Die Toast bleibt stehen,
          // bis sie angetippt wird (→ PIN) oder ein Foto gestartet wird.
          if (shutdownActive) { break; }
          if (toastKind === "update_offer" || toastKind === "update_run") { break; }
          if (!screenIdle.classList.contains("active")) { break; }
          if (pinModal.classList.contains("show")) { break; }
          showToast({
            icon: "update",
            title: "Update verfügbar",
            message: "Antippen zum Installieren",
            progress: false,
            autohide: 0,
            kind: "update_offer"
          });
          break;

        case "update_progress":
          showToast({
            icon: "spinner",
            title: "Update läuft",
            message: msg.data.message || "",
            progress: true,
            percent: msg.data.percent || 0,
            autohide: 0,
            kind: "update_run"
          });
          break;

        case "update_failed":
          showToast({
            icon: "cross",
            title: "Update fehlgeschlagen",
            message: msg.data.message || "",
            variant: "error",
            progress: false,
            autohide: 8000
          });
          break;

        case "camera_power":
          // Wechsel des Lade-/Akkustatus der Kamera (USB-Strom).
          if (msg.data.charging) {
            showToast({
              icon: "link",
              title: "Kamera lädt",
              message: "Stromversorgung über USB erkannt",
              progress: false,
              autohide: 4000
            });
          } else {
            showToast({
              icon: "unlink",
              title: "Kamera am Akku",
              message: "Keine USB-Stromversorgung mehr",
              variant: "error",
              progress: false,
              autohide: 4000
            });
          }
          break;
      }
    };

    source.onerror = function () {
      source.close();
      setTimeout(connectSSE, 3000);
    };
  }

  function startCountdownScreen() {
    // Foto geht vor: ein offenes Update-Angebot verschwindet jetzt (erst
    // jetzt – die Toast hat keinen Timeout) und der Ablauf läuft normal.
    if (toastKind === "update_offer") { hideToast(); }
    showScreen(screenCountdown);
    startCountdown();
  }

  // ── Review button handlers ────────────────────────────

  if (btnMorePhotos) {
    btnMorePhotos.addEventListener("click", function () {
      returnToIdle();
    });
  }

  if (btnDone) {
    btnDone.addEventListener("click", function () {
      btnDone.disabled = true;
      fetch("/session/finish", { method: "POST" })
        .then(function (res) {
          return res.json().then(function (data) {
            if (!res.ok) { throw new Error(data.error || "Session konnte nicht beendet werden"); }
            return data;
          });
        })
        .then(function (data) {
          // Hotspot: zwei Seiten (Schritt 1 WLAN → Weiter → Schritt 2 Download)
          qrCodeImg.src = data.wifi_qr;
          qrDownloadImg.src = data.download_qr;
          qrSsid.textContent = data.ssid;
          qrPassword.textContent = data.password;
          qrUrl.textContent = data.download_url;

          showScreen(screenQr);
          showQrPage("box-wifi");  // immer mit Schritt 1 starten (kein Timeout)
        })
        .catch(function (err) {
          console.error("session/finish error:", err);
          errorMessage.textContent = err.message || "Verbindungsfehler";
          showScreen(screenError);
          setTimeout(returnToIdle, 5000);
        })
        .finally(function () {
          btnDone.disabled = false;
        });
    });
  }

  // ── Auslösen per Touch (ganzer Startbildschirm) ───────
  // Ein Tipp irgendwo auf den Startbildschirm startet den Countdown – nicht
  // nur das Kamera-Icon (größere Trefferfläche, zuverlässiger auf Touch).
  // AUSNAHME: das obere rechte Drittel. 5 Taps dort innerhalb von 4 s öffnen
  // das Shutdown-Menü; einzelne Taps dort lösen NIE ein Foto aus.

  var CORNER_TAPS = 5;
  var CORNER_WINDOW_MS = 4000;
  var cornerTimestamps = [];

  screenIdle.addEventListener("click", function (e) {
    if (shutdownActive || pinModal.classList.contains("show")) { return; }

    var inCorner = e.clientX > window.innerWidth * 2 / 3 &&
                   e.clientY < window.innerHeight / 3;
    if (inCorner) {
      var now = Date.now();
      cornerTimestamps.push(now);
      cornerTimestamps = cornerTimestamps.filter(function (t) {
        return now - t <= CORNER_WINDOW_MS;
      });
      if (cornerTimestamps.length >= CORNER_TAPS) {
        cornerTimestamps = [];
        openShutdownMenu();
      }
      return;
    }

    fetch("/trigger", { method: "POST" })
      .catch(function (err) { console.error("Trigger error:", err); });
  });

  connectSSE();
})();
