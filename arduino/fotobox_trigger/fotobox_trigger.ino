/*
 * Fotobox Trigger – Arduino Nano Firmware
 * WITH AWESOME LED EFFECTS 🔥
 *
 * Controls a physical button and a WS2812 LED ring.
 * Communicates with the Raspberry Pi over USB serial.
 */

#include <Adafruit_NeoPixel.h>

// === Pin Configuration ===
#define BUTTON_PIN    2
#define LED_PIN       6
#define NUM_LEDS      12

// === Timing ===
#define DEBOUNCE_MS       1000
#define COUNTDOWN_STEP_MS 500   // 0.5 s per LED
#define IDLE_DELAY_MS     20    // Animations-Speed für den Regenbogen

// === Shutdown-Geste ===
// 5× schnell tippen (auch WÄHREND des Countdowns) öffnet auf dem Pi das
// Shutdown-Menü. Damit das funktioniert, wird der Button auch im Countdown
// gepollt und jeder Tap als "button_pressed" gemeldet; beim Erreichen der
// Schwelle wird der Countdown abgebrochen (kein Foto).
#define SHUTDOWN_TAPS       5
#define SHUTDOWN_WINDOW_MS  4000
#define TAP_DEBOUNCE_MS     120   // schnelle Taps zulassen (nicht 1000 ms)

// === LED Colors ===
#define COLOR_BLUE   strip.Color(0, 0, 255)
#define COLOR_ORANGE strip.Color(255, 100, 0)
#define COLOR_RED    strip.Color(255, 0, 0)
#define COLOR_WHITE  strip.Color(255, 255, 255) // Weiß für den krassen Blitz!
#define COLOR_WHITE2  strip.Color(255, 150, 150) // Weiß für den krassen Blitz!

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

enum State { IDLE, COUNTDOWN };
State currentState = IDLE;

unsigned long lastButtonPress = 0;
uint16_t rainbowHue = 0; // Speicher für die rotierende Idle-Farbe

// Tap-Zähler für die Shutdown-Geste (gültig über IDLE- und COUNTDOWN-Phase).
int           tapCount = 0;
unsigned long lastTapTime = 0;       // Zeitpunkt des letzten gezählten Taps
unsigned long lastEdgeTime = 0;      // Entprellung der Flankenerkennung
int           lastButtonReading = LOW;  // gedrückt = HIGH

// ── Helpers ──────────────────────────────────────────────

// Flankenerkennung: liefert genau einmal true, wenn der Button neu gedrückt
// wird (LOW→HIGH), inklusive kurzer Entprellung für schnelles Tippen.
bool pollButtonTap() {
  int reading = digitalRead(BUTTON_PIN);
  bool tapped = false;
  if (reading == HIGH && lastButtonReading == LOW) {
    unsigned long now = millis();
    if (now - lastEdgeTime > TAP_DEBOUNCE_MS) {
      lastEdgeTime = now;
      tapped = true;
    }
  }
  lastButtonReading = reading;
  return tapped;
}

// Zählt einen erkannten Tap auf das Shutdown-Fenster und meldet ihn an den Pi.
// Gibt true zurück, wenn die Tap-Schwelle erreicht ist (→ Countdown abbrechen).
bool registerTap() {
  unsigned long now = millis();
  if (now - lastTapTime > SHUTDOWN_WINDOW_MS) {
    tapCount = 0;  // Fenster abgelaufen – von vorn zählen
  }
  lastTapTime = now;
  tapCount++;
  Serial.println("button_pressed");  // füttert die Burst-Erkennung im Browser
  return tapCount >= SHUTDOWN_TAPS;
}

// Wartet ms Millisekunden und pollt dabei den Button. Gibt true zurück, wenn
// die Shutdown-Schwelle erreicht wurde (Aufrufer soll den Countdown abbrechen).
bool interruptibleDelay(unsigned long ms) {
  unsigned long start = millis();
  while (millis() - start < ms) {
    if (pollButtonTap()) {
      if (registerTap()) { return true; }
    }
    delay(2);
  }
  return false;
}

// Wartet, bis der Button losgelassen ist (verhindert sofortiges Re-Triggern).
void waitForRelease() {
  while (digitalRead(BUTTON_PIN) == HIGH) { delay(5); }
  lastButtonReading = LOW;
}

void setAllLeds(uint32_t color) {
  for (int i = 0; i < NUM_LEDS; i++) {
    strip.setPixelColor(i, color);
  }
  strip.show();
}

void clearLeds() {
  strip.clear();
  strip.show();
}

uint32_t countdownColor(int step) {
  /*  0-2  → blue
   *  3-5  → orange
   *  6-7  → red              */
  if (step < 3) return COLOR_BLUE;
  if (step < 6) return COLOR_ORANGE;
  return COLOR_RED;
}

// ── KRASSE ANIMATIONEN ───────────────────────────────────

// 1. Boot-Animation (Scanner / Knight Rider)
void bootAnimation() {
  for (int j = 0; j < 2; j++) {
    for (int i = 0; i < NUM_LEDS; i++) {
      clearLeds();
      strip.setPixelColor(i, COLOR_BLUE);
      // Cooler Licht-Schweif
      if (i > 0) strip.setPixelColor(i - 1, strip.Color(0, 0, 100));
      if (i > 1) strip.setPixelColor(i - 2, strip.Color(0, 0, 20));
      strip.show();
      delay(500);
    }
  }
  clearLeds();

    for (int j = 0; j < 2; j++) {
    for (int i = 0; i < NUM_LEDS; i++) {
      clearLeds();
      strip.setPixelColor(i, COLOR_BLUE);
      // Cooler Licht-Schweif
      if (i > 0) strip.setPixelColor(i - 1, strip.Color(0, 0, 100));
      if (i > 1) strip.setPixelColor(i - 2, strip.Color(0, 0, 20));
      strip.show();
      delay(500);
    }
  }
  clearLeds();
}

// 2. Weicher, rotierender Regenbogen für den Standby
void idleAnimation() {
  strip.setBrightness(15); 
  for(int i = 0; i < NUM_LEDS; i++) {
    // Berechnet die Farbverschiebung pro LED
    int pixelHue = rainbowHue + (i * 65536L / NUM_LEDS);
    // gamma32 macht die Farbübergänge viel satter und realistischer
    strip.setPixelColor(i, strip.gamma32(strip.ColorHSV(pixelHue)));
  }
  strip.show();
  rainbowHue += 256; // Geschwindigkeit der Rotation
  delay(IDLE_DELAY_MS);
}

// 3. Roulette Spin-Up (Wird direkt nach Button-Press getriggert)
// Gibt true zurück, wenn die Shutdown-Geste den Vorgang abbrechen soll.
bool spinUpEffect() {
  int delayTime = 80;
  // Dreht sich 2 Runden und wird dabei immer schneller
  for (int i = 0; i < NUM_LEDS * 2; i++) {
    clearLeds();
    strip.setPixelColor(i % NUM_LEDS, COLOR_WHITE);
    // Leichter Schweif
    strip.setPixelColor((i + NUM_LEDS - 1) % NUM_LEDS, strip.Color(50, 50, 50));
    strip.show();
    if (interruptibleDelay(delayTime)) { return true; }
    delayTime -= 4; // Beschleunigung!
    if (delayTime < 15) delayTime = 15;
  }
  return false;
}

// 4. Foto-Blitz Effekt (Auslösung!)
void flashEffect() {
  // BAM! Maximale Helligkeit für den Foto-Moment
  strip.setBrightness(255); 
  setAllLeds(COLOR_WHITE);
  delay(450); // Greller Blitz für 150ms
  clearLeds();
  strip.setBrightness(0); // Zurück zur Standard-Helligkeit
  delay(250); // Greller Blitz für 150ms
  clearLeds();
    strip.setBrightness(255); 
  setAllLeds(COLOR_WHITE);
  delay(350); // Greller Blitz für 150ms
  strip.setBrightness(80); // Zurück zur Standard-Helligkeit
}

// ── Countdown ────────────────────────────────────────────

// Gibt true zurück, wenn der Countdown durch die Shutdown-Geste (5× Tippen)
// abgebrochen wurde – dann darf KEIN Foto ausgelöst werden.
bool runCountdown() {
  // Spannungsaufbau vor dem Start
  strip.setBrightness(200);

  if (spinUpEffect()) { clearLeds(); return true; }


  // Dein Countdown läuft...
  for (int i = NUM_LEDS - 1; i >= 0; i--) {
    uint32_t color = countdownColor(NUM_LEDS - 1 - i);

    // LEDs bis zum aktuellen Stand setzen
    for (int j = 0; j < NUM_LEDS; j++) {
      if (j <= i) strip.setPixelColor(j, color);
      else strip.setPixelColor(j, 0);
    }
    strip.show();

    // "Ticking Bomb" Effekt: Die aktive LED blitzt weiß auf
    strip.setPixelColor(i, COLOR_WHITE);
    strip.show();
    if (interruptibleDelay(80)) { clearLeds(); return true; }

    // Wieder zurück zur Countdown-Farbe
    strip.setPixelColor(i, color);
    strip.show();

    // Restliche Zeit warten (damit es exakt bei deinen 500ms bleibt!)
    if (interruptibleDelay(COUNTDOWN_STEP_MS - 80)) { clearLeds(); return true; }
  }

  clearLeds();
  return false;
}

// ── Setup & Loop ─────────────────────────────────────────

void setup() {
  Serial.begin(9600);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  strip.begin();
  strip.setBrightness(80); // Normale Helligkeit
  clearLeds();

  // Zeig den Gästen, dass das System hochfährt
  bootAnimation();

  currentState = IDLE;
}

void loop() {
  switch (currentState) {

    case IDLE:
      idleAnimation();

      if (digitalRead(BUTTON_PIN) == HIGH) {
        unsigned long now = millis();
        if (now - lastButtonPress > DEBOUNCE_MS) {
          lastButtonPress = now;
          lastButtonReading = HIGH;   // Flankenerkennung synchronisieren
          registerTap();              // sendet button_pressed, tapCount = 1
          currentState = COUNTDOWN;
        }
      }
      break;

    case COUNTDOWN:
      if (runCountdown()) {
        // Durch 5× Tippen abgebrochen: KEIN countdown_complete, kein Blitz,
        // kein Foto. Der Pi hat über die button_pressed-Taps bereits das
        // Shutdown-Menü geöffnet.
        clearLeds();
      } else {
        // Countdown regulär fertig -> Sag dem Raspberry Pi Bescheid
        Serial.println("countdown_complete");
        // Und exakt JETZT den krassen LED-Blitz zünden! 📸
        flashEffect();
      }

      tapCount = 0;        // Zähler für die nächste Runde zurücksetzen
      waitForRelease();    // Prellen/Halten nicht als neuen Tap werten
      currentState = IDLE;
      break;
  }
}
