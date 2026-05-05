#include <Adafruit_NeoPixel.h>

// --- Pin Assignments ---
// Node_L: Out=0, In=1
// Node_R: Out=6, In=5
// NONE (Main): Out=2, In=None
const int OUT_PINS[3] = {1, 6, 2}; 
const int IN_PINS[3]  = {0, 7, -1}; // -1 means no sensor

const int LED_PIN = 4;
const int NUM_PIXELS = 2;
Adafruit_NeoPixel pixels(NUM_PIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);

void setupPins() {
  pixels.begin();
  pixels.setBrightness(50);
  updateLEDStatus("IDLE");
  
  for(int i = 0; i < 3; i++) {
    digitalWrite(OUT_PINS[i], LOW); 
    pinMode(OUT_PINS[i], OUTPUT);
    
    if (IN_PINS[i] != -1) {
      pinMode(IN_PINS[i], INPUT_PULLUP); // Assumes sensor pulls to GND
    }
  }
}
extern bool isDiscovered;
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

void executeCommand(String target, String value) {
  if (!isDiscovered) {
    Serial.println("BLOCKED: Command ignored. Base not discovered yet.");
    return;
  }

  int signal = (value.equalsIgnoreCase("high")) ? LOW : HIGH;

  if (target == "base") {
    for(int i = 0; i < 3; i++) digitalWrite(OUT_PINS[i], signal);
  } 
  else {
    int pinIdx = -1;
    if (target == "node_l") pinIdx = 0;
    else if (target == "node_r") pinIdx = 1;
    else if (target == "node_c") pinIdx = 2;

    if (pinIdx != -1) digitalWrite(OUT_PINS[pinIdx], signal);
  }
}

bool isNodeAttached(int index) {
  return (IN_PINS[index] != -1 && digitalRead(IN_PINS[index]) == LOW);
}

bool isNodeOn(int index) {
  return (digitalRead(OUT_PINS[index]) == LOW);
}

void triggerTotalShutdown() {
  for(int i = 0; i < 3; i++) digitalWrite(OUT_PINS[i], LOW);
}
