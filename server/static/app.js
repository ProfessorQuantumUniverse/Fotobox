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
  var flashOverlay    = document.getElementById("flash-overlay");
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

  // Shutdown-Menü
  var btnShutdownCancel  = document.getElementById("btn-shutdown-cancel");
  var btnShutdownConfirm = document.getElementById("btn-shutdown-confirm");

  function showQrPage(id) {
    var pages = document.querySelectorAll(".qr-page");
    for (var i = 0; i < pages.length; i++) {
      pages[i].classList.toggle("active", pages[i].id === id);
    }
  }

  if (btnQrNext) {
    btnQrNext.addEventListener("click", function () { showQrPage("box-download"); });
  }
  if (btnQrBack) {
    btnQrBack.addEventListener("click", function () { showQrPage("box-wifi"); });
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
    cross: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
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

  function showToast(opts) {
    // opts: { icon, title, message, percent (number|null), variant, progress (bool), autohide (ms|0) }
    if (toastHideTimer) { clearTimeout(toastHideTimer); toastHideTimer = null; }

    toast.classList.remove("toast-error");
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
    toast.classList.remove("show");
  }

  function triggerFlash() {
    flashOverlay.classList.remove("flash");
    // Reflow erzwingen, damit die Animation erneut startet
    void flashOverlay.offsetWidth;
    flashOverlay.classList.add("flash");
  }

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
          triggerFlash();
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

        case "update_done":
          // Server schickt dieses Event NUR, wenn wirklich eine neue Version
          // geladen wurde. Alles andere läuft still im Hintergrund.
          showToast({
            icon: "check",
            title: "Update installiert",
            message: msg.data.message || "Neue Version aktiv",
            progress: false,
            autohide: 5000
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

          showQrPage("box-wifi");  // immer mit Schritt 1 starten
          showScreen(screenQr);
          // Auto-Rückkehr zur Homepage – egal auf welcher Folie. Dabei wird
          // der Hotspot abgebaut. Fällt die Konfig auf 0/leer, greift ein
          // sicherer Default, damit der QR-Screen NIE dauerhaft hängen bleibt.
          var qrSecs = (window.QR_TIMEOUT_SECONDS && QR_TIMEOUT_SECONDS > 0) ? QR_TIMEOUT_SECONDS : 120;
          qrTimeout = setTimeout(function () {
            fetch("/session/stop-ap", { method: "POST" })
              .catch(function (err) { console.error("stop-ap error:", err); });
            returnToIdle();
          }, qrSecs * 1000);
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

  // ── WebUI Trigger ────────────────────────────────────

  var triggerBtn = document.getElementById("trigger-btn");
  if (triggerBtn) {
    triggerBtn.addEventListener("click", function () {
      fetch("/trigger", { method: "POST" })
        .catch(function (err) { console.error("Trigger error:", err); });
    });
  }

  connectSSE();
})();
