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
  var btnNewSession = document.getElementById("btn-new-session");

  var countdownInterval = null;
  var reviewTimeout = null;
  var qrTimeout = null;

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

  function showScreen(screen) {
    clearTimers();
    [screenIdle, screenCountdown, screenReview, screenQr, screenError].forEach(function (s) {
      s.classList.remove("active");
    });
    screen.classList.add("active");
  }

  function returnToIdle() {
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
          startCountdownScreen();
          break;

        case "countdown_complete":
          triggerFlash();
          break;

        case "photo_taken":
          // Downskalierte Preview laden – volle DSLR-Auflösung überfordert
          // den Browser auf dem Pi 3.
          reviewPhoto.src = "/photos/preview/" + encodeURIComponent(msg.data.filename);
          showScreen(screenReview);
          startReviewTimer();
          break;

        case "error":
          errorMessage.textContent = msg.data.message || "Unbekannter Fehler";
          showScreen(screenError);
          setTimeout(returnToIdle, 5000);
          break;

        case "ethernet_connected":
          showToast({
            icon: "link",
            title: "LAN verbunden",
            message: "Suche nach Updates …",
            progress: false,
            autohide: 0
          });
          break;

        case "ethernet_disconnected":
          // Cable raus → laufendes Update wird serverseitig zurückgerollt.
          showToast({
            icon: "unlink",
            title: "LAN getrennt",
            message: "Vorherige Version bleibt aktiv",
            variant: "error",
            progress: false,
            autohide: 4000
          });
          break;

        case "update_progress":
          showToast({
            icon: "spinner",
            title: "Update läuft",
            message: msg.data.message || "Lade herunter …",
            percent: msg.data.percent,
            progress: true,
            autohide: 0
          });
          updateToastProgress(msg.data.percent, msg.data.message);
          break;

        case "update_done":
          if (msg.data.success) {
            updateToastProgress(100, msg.data.message);
            showToast({
              icon: "check",
              title: "Update fertig",
              message: msg.data.message || "Aktuell",
              percent: 100,
              progress: true,
              autohide: 4500
            });
          } else {
            showToast({
              icon: "cross",
              title: "Update fehlgeschlagen",
              message: msg.data.message || "Bitte später erneut versuchen",
              variant: "error",
              progress: false,
              autohide: 6000
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
          var boxWifi = document.getElementById("box-wifi");
          var instructionDownload = document.getElementById("instruction-download");
          var stepNumberDownload = document.getElementById("step-number-download");

          if (data.share_mode === "nextcloud") {
            // Nextcloud: nur ein QR-Code, kein WLAN-Schritt
            boxWifi.style.display = "none";
            stepNumberDownload.textContent = "1";
            instructionDownload.textContent = "Code mit der Kamera-App scannen";
            qrDownloadImg.src = data.download_qr;
            qrUrl.textContent = "";
          } else {
            // Hotspot: zwei Schritte untereinander (WLAN, dann Download)
            boxWifi.style.display = "flex";
            stepNumberDownload.textContent = "2";
            instructionDownload.textContent = "Code scannen und Fotos herunterladen";
            qrCodeImg.src = data.wifi_qr;
            qrDownloadImg.src = data.download_qr;
            qrSsid.textContent = data.ssid;
            qrPassword.textContent = data.password;
            qrUrl.textContent = data.download_url;
          }

          showScreen(screenQr);
          if (window.QR_TIMEOUT_SECONDS && QR_TIMEOUT_SECONDS > 0) {
            qrTimeout = setTimeout(returnToIdle, QR_TIMEOUT_SECONDS * 1000);
          }
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

  // ── QR screen: start new session ────────────────────

  if (btnNewSession) {
    btnNewSession.addEventListener("click", function () {
      fetch("/session/stop-ap", { method: "POST" })
        .catch(function (err) { console.error("stop-ap error:", err); });
      returnToIdle();
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
