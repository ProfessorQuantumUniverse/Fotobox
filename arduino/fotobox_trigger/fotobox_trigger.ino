/*
 * Fotobox Trigger – Arduino Nano Firmware
 *
 * Controls a physical button and a WS2812 LED ring.
 * Communicates with the Raspberry Pi over USB serial.
 *
 * Wiring:
 *   - Button: Pin 2 → GND (internal pull-up)
 *   - LED Ring (WS2812): Pin 6, shared GND + 5V
 *
 * Serial protocol (9600 baud):
 *   Arduino → RPi: "button_pressed"    (button was pressed)
 *   Arduino → RPi: "countdown_complete" (countdown finished, take photo)
 */

#include <Adafruit_NeoPixel.h>

// === Pin Configuration ===
#define BUTTON_PIN    2
#define LED_PIN       6
#define NUM_LEDS      8

// === Timing ===
#define DEBOUNCE_MS       200
#define COUNTDOWN_STEP_MS 500   // 0.5 s per LED
#define IDLE_PULSE_MS     30    // pulse animation speed

// === LED Colors ===
#define COLOR_BLUE   strip.Color(0, 0, 255)
#define COLOR_ORANGE strip.Color(255, 100, 0)
#define COLOR_RED    strip.Color(255, 0, 0)
#define COLOR_WHITE  strip.Color(60, 60, 60)

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

enum State { IDLE, COUNTDOWN };
State currentState = IDLE;

unsigned long lastButtonPress = 0;
uint8_t pulseBrightness = 0;
int8_t  pulseDirection  = 1;

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

// ── Idle Pulse ───────────────────────────────────────────

void idlePulse() {
  pulseBrightness += pulseDirection * 2;
  if (pulseBrightness >= 60 || pulseBrightness <= 0) {
    pulseDirection = -pulseDirection;
    pulseBrightness = constrain(pulseBrightness, 0, 60);
  }
  uint32_t c = strip.Color(pulseBrightness, pulseBrightness, pulseBrightness);
  setAllLeds(c);
  delay(IDLE_PULSE_MS);
}

// ── Countdown ────────────────────────────────────────────

void runCountdown() {
  // Light up all LEDs in blue first
  setAllLeds(COLOR_BLUE);
  delay(200);

  // Turn off LEDs one by one
  for (int i = NUM_LEDS - 1; i >= 0; i--) {
    // Update remaining LEDs to current phase color
    uint32_t color = countdownColor(NUM_LEDS - 1 - i);
    for (int j = 0; j <= i; j++) {
      strip.setPixelColor(j, color);
    }
    // Clear LEDs already counted
    for (int j = i + 1; j < NUM_LEDS; j++) {
      strip.setPixelColor(j, 0);
    }
    strip.show();
    delay(COUNTDOWN_STEP_MS);
  }

  clearLeds();
}

// ── Setup & Loop ─────────────────────────────────────────

void setup() {
  Serial.begin(9600);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  strip.begin();
  strip.setBrightness(80);
  clearLeds();

  currentState = IDLE;
}

void loop() {
  switch (currentState) {

    case IDLE:
      idlePulse();

      if (digitalRead(BUTTON_PIN) == LOW) {
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
      Serial.println("countdown_complete");
      currentState = IDLE;
      break;
  }
}
