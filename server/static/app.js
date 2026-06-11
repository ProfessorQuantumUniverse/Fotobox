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

  // ── Ball-Physics-Ladeanimation ────────────────────────

  function startBallAnimation(canvas) {
    var W = canvas.width, H = canvas.height;
    var ctx = canvas.getContext("2d");
    var raf = null;
    var running = true;

    var N = 11;
    var balls = [];
    for (var i = 0; i < N; i++) {
      var r = 8 + Math.random() * 22;
      balls.push({
        x: r + Math.random() * (W - 2 * r),
        y: -r * 3 - Math.random() * H * 0.9,
        vx: (Math.random() - 0.5) * 3.5,
        vy: Math.random() * 2,
        r: r,
        m: r * r,
      });
    }

    var G = 0.38, REST = 0.52, AIR = 0.985, GFRIC = 0.84;

    function step() {
      if (!running) return;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, W, H);

      for (var i = 0; i < balls.length; i++) {
        var b = balls[i];
        b.vy += G;
        b.vx *= AIR;
        b.x += b.vx;
        b.y += b.vy;
        if (b.x - b.r < 0)  { b.x = b.r;     b.vx =  Math.abs(b.vx) * REST; }
        if (b.x + b.r > W)  { b.x = W - b.r; b.vx = -Math.abs(b.vx) * REST; }
        if (b.y + b.r > H)  { b.y = H - b.r; b.vy = -Math.abs(b.vy) * REST; b.vx *= GFRIC; }
      }

      for (var i = 0; i < balls.length; i++) {
        for (var j = i + 1; j < balls.length; j++) {
          var a = balls[i], b2 = balls[j];
          var dx = b2.x - a.x, dy = b2.y - a.y;
          var d2 = dx * dx + dy * dy;
          var md = a.r + b2.r;
          if (d2 < md * md && d2 > 0.001) {
            var d = Math.sqrt(d2);
            var nx = dx / d, ny = dy / d;
            var sep = (md - d) * 0.5;
            var mt = a.m + b2.m;
            a.x  -= nx * sep * (b2.m / mt);
            a.y  -= ny * sep * (b2.m / mt);
            b2.x += nx * sep * (a.m  / mt);
            b2.y += ny * sep * (a.m  / mt);
            var dvx = a.vx - b2.vx, dvy = a.vy - b2.vy;
            var dot = dvx * nx + dvy * ny;
            if (dot > 0) {
              var imp = 2 * dot / mt * REST;
              a.vx  -= imp * b2.m * nx;  a.vy  -= imp * b2.m * ny;
              b2.vx += imp * a.m  * nx;  b2.vy += imp * a.m  * ny;
            }
          }
        }
      }

      for (var i = 0; i < balls.length; i++) {
        var b = balls[i];
        if (b.y + b.r <= 0) continue;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fillStyle = "#fff";
        ctx.fill();
      }

      raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);

    return function () {
      running = false;
      if (raf) { cancelAnimationFrame(raf); raf = null; }
    };
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
          (function (filename) {
            var loader    = document.getElementById("review-loader");
            var photoFrame = document.getElementById("photo-frame");
            // Zustände zurücksetzen
            loader.classList.remove("done");
            photoFrame.classList.remove("loaded");
            reviewPhoto.onload = null;
            reviewPhoto.src = "";

            showScreen(screenReview);

            var cancelled = false;
            var stopAnim  = null;

            // Canvas nach dem ersten Layout-Pass befüllen
            requestAnimationFrame(function () {
              if (cancelled) return;
              loader.width  = loader.clientWidth  || 600;
              loader.height = loader.clientHeight || 400;
              stopAnim = startBallAnimation(loader);
            });

            reviewPhoto.onload = function () {
              cancelled = true;
              if (stopAnim) { stopAnim(); }
              loader.classList.add("done");
              photoFrame.classList.add("loaded");
              startReviewTimer();
            };
            reviewPhoto.onerror = function () {
              cancelled = true;
              if (stopAnim) { stopAnim(); }
              loader.classList.add("done");
              photoFrame.classList.add("loaded");
              startReviewTimer();
            };
            reviewPhoto.src = "/photos/preview/" + encodeURIComponent(filename);
          }(msg.data.filename));
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

          // Hotspot: zwei Schritte untereinander (WLAN, dann Download)
          boxWifi.style.display = "flex";
          stepNumberDownload.textContent = "2";
          instructionDownload.textContent = "Code scannen und Fotos herunterladen";
          qrCodeImg.src = data.wifi_qr;
          qrDownloadImg.src = data.download_qr;
          qrSsid.textContent = data.ssid;
          qrPassword.textContent = data.password;
          qrUrl.textContent = data.download_url;

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
