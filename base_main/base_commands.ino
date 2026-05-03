#include <Adafruit_NeoPixel.h>

// --- Pin Assignments ---
// Node_L: Out=0, In=1
// Node_R: Out=6, In=5
// NONE (Main): Out=2, In=None
const int OUT_PINS[3] = {0, 6, 2}; 
const int IN_PINS[3]  = {1, 5, -1}; // -1 means no sensor

const int LED_PIN = 4;
const int NUM_PIXELS = 2;
Adafruit_NeoPixel pixels(NUM_PIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);

void setupPins() {
  pixels.begin();
  pixels.setBrightness(50);
  
  for(int i = 0; i < 3; i++) {
    pinMode(OUT_PINS[i], OUTPUT);
    digitalWrite(OUT_PINS[i], HIGH); // Active Low: HIGH is OFF
    
    // Configure Input Pins
    if (IN_PINS[i] != -1) {
      pinMode(IN_PINS[i], INPUT_PULLUP); // Assumes sensor pulls to GND
    }
  }
}

void updateLEDStatus(String status) {
  uint32_t color;
  if (status == "IDLE")      color = pixels.Color(255, 255, 255);
  else if (status == "PAIRED") color = pixels.Color(0, 255, 0);
  else if (status == "SAFE_MODE") color = pixels.Color(255, 255, 0);
  else if (status == "UPDATING") color = pixels.Color(0, 255, 255);
  else color = pixels.Color(0, 0, 0);

  pixels.fill(color);
  pixels.show();
  Serial.println("LED Status updated to: " + status);
}

// Helper to check if a node is physically attached (In Pin)
bool isNodeAttached(int index) {
  if (IN_PINS[index] == -1) return false; // Main node has no sensor
  return digitalRead(IN_PINS[index]) == LOW; // Assumes LOW = Attached
}

// Helper to check if a node is currently powered (Out Pin)
bool isNodeOn(int index) {
  return digitalRead(OUT_PINS[index]) == LOW; // Active Low
}

void executeCommand(String target, String value) {
  int signal = (value.equalsIgnoreCase("High")) ? LOW : HIGH;
  int pinIdx = -1;

  if (target == "Base_1") {
    for(int i = 0; i < 3; i++) digitalWrite(OUT_PINS[i], signal);
    return;
  }
  
  if (target == "Node_L") pinIdx = 0;
  else if (target == "Node_R") pinIdx = 1;
  else if (target == "NONE") pinIdx = 2;

  if (pinIdx != -1) digitalWrite(OUT_PINS[pinIdx], signal);
}

void triggerTotalShutdown() {
  for(int i = 0; i < 3; i++) digitalWrite(OUT_PINS[i], HIGH);
}
