/* Fotobox – Frontend logic (SSE-driven state machine) */

(function () {
  "use strict";

  // Screen elements
  const screenIdle      = document.getElementById("screen-idle");
  const screenCountdown = document.getElementById("screen-countdown");
  const screenReview    = document.getElementById("screen-review");
  const screenError     = document.getElementById("screen-error");
  const reviewPhoto     = document.getElementById("review-photo");
  const errorMessage    = document.getElementById("error-message");
  const countdownDots   = document.getElementById("countdown-dots");

  let reviewTimeout = null;

  // ── Helpers ──────────────────────────────────────────

  function showScreen(screen) {
    [screenIdle, screenCountdown, screenReview, screenError].forEach(function (s) {
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
    if (reviewTimeout) {
      clearTimeout(reviewTimeout);
      reviewTimeout = null;
    }
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
          reviewTimeout = setTimeout(returnToIdle, (typeof REVIEW_SECONDS !== "undefined" ? REVIEW_SECONDS : 5) * 1000);
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

  connectSSE();
})();
