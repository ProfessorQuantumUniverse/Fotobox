/* Fotobox – Frontend logic (SSE-driven state machine) */

(function () {
  "use strict";

  // Screen elements
  const screenIdle      = document.getElementById("screen-idle");
  const screenCountdown = document.getElementById("screen-countdown");
  const screenReview    = document.getElementById("screen-review");
  const screenQr        = document.getElementById("screen-qr");
  const screenError     = document.getElementById("screen-error");
  const reviewPhoto     = document.getElementById("review-photo");
  const errorMessage    = document.getElementById("error-message");
  const countdownDots   = document.getElementById("countdown-dots");

  // Review buttons
  const btnMorePhotos   = document.getElementById("btn-more-photos");
  const btnDone         = document.getElementById("btn-done");

  // QR screen elements
  const qrCodeImg       = document.getElementById("qr-code-img");
  const qrSsid          = document.getElementById("qr-ssid");
  const qrPassword      = document.getElementById("qr-password");
  const qrUrl           = document.getElementById("qr-url");
  const btnNewSession   = document.getElementById("btn-new-session");

  // ── Helpers ──────────────────────────────────────────

  function showScreen(screen) {
    [screenIdle, screenCountdown, screenReview, screenQr, screenError].forEach(function (s) {
      s.classList.remove("active");
    });
    screen.classList.add("active");
  }

  function buildDots(count) {
    countdownDots.innerHTML = "";
    for (let i = 0; i < count; i++) {
      const dot = document.createElement("div");
      dot.className = "dot";
      countdownDots.appendChild(dot);
    }
  }

  function returnToIdle() {
    showScreen(screenIdle);
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
          buildDots(8);
          showScreen(screenCountdown);
          break;

        case "countdown_complete":
          // waiting for photo…
          break;

        case "photo_taken":
          reviewPhoto.src = "/photos/" + msg.data.filename;
          showScreen(screenReview);
          break;

        case "error":
          errorMessage.textContent = msg.data.message || "Unbekannter Fehler";
          showScreen(screenError);
          setTimeout(returnToIdle, 4000);
          break;
      }
    };

    source.onerror = function () {
      source.close();
      setTimeout(connectSSE, 3000);
    };
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
        .then(function (res) { return res.json(); })
        .then(function (data) {
          qrCodeImg.src = data.qr;
          qrSsid.textContent = data.ssid;
          qrPassword.textContent = data.password;
          qrUrl.textContent = data.url;
          showScreen(screenQr);
        })
        .catch(function (err) {
          console.error("session/finish error:", err);
          returnToIdle();
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
  const triggerBtn = document.getElementById("trigger-btn");
  if (triggerBtn) {
    triggerBtn.addEventListener("click", function() {
      fetch("/trigger", { method: "POST" })
        .catch(err => console.error("Trigger error:", err));
    });
  }

  connectSSE();
})();
