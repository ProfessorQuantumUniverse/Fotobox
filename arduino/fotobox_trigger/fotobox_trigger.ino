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

// ── Helpers ──────────────────────────────────────────────

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
void spinUpEffect() {
  int delayTime = 80;
  // Dreht sich 2 Runden und wird dabei immer schneller
  for (int i = 0; i < NUM_LEDS * 2; i++) {
    clearLeds();
    strip.setPixelColor(i % NUM_LEDS, COLOR_WHITE);
    // Leichter Schweif
    strip.setPixelColor((i + NUM_LEDS - 1) % NUM_LEDS, strip.Color(50, 50, 50));
    strip.show();
    delay(delayTime);
    delayTime -= 4; // Beschleunigung!
    if (delayTime < 15) delayTime = 15;
  }
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

void runCountdown() {
  // Spannungsaufbau vor dem Start
  strip.setBrightness(200); 

  spinUpEffect();


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
    delay(80);
    
    // Wieder zurück zur Countdown-Farbe
    strip.setPixelColor(i, color);
    strip.show();

    // Restliche Zeit warten (damit es exakt bei deinen 500ms bleibt!)
    delay(COUNTDOWN_STEP_MS - 80);
  }

  clearLeds();
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

      // (Logik exakt beibehalten, da sie bei dir perfekt läuft!)
      if (digitalRead(BUTTON_PIN) == HIGH) {
        unsigned long now = millis();
        if (now - lastButtonPress > DEBOUNCE_MS) {
          lastButtonPress = now;
          Serial.println("button_pressed");
          currentState = COUNTDOWN;
        }
      }
      break;

    case COUNTDOWN:
      runCountdown();
      
      // Countdown ist fertig -> Sag dem Raspberry Pi Bescheid
      Serial.println("countdown_complete");
      
      // Und exakt JETZT den krassen LED-Blitz zünden! 📸
      flashEffect();
      
      currentState = IDLE;
      break;
  }
}
