#include <WiFi.h>

// Global System States
const String LOCK_CODE = "87654321"; // Predetermined "Key" for each Base
bool isPaired = false;
String receivedSsid = ""; // Storage for WiFi name from Hub
String receivedPass = ""; // Storage for WiFi Password from Hub

// Functions
void handlePairing();        
void monitorHeartbeat();     
void executeCommand(String cmd); 
void setupPins();            
void triggerTotalShutdown();

void setup() {
  Serial.begin(115200);
  setupPins(); // Defined in base_commands.ino
  Serial.println("--- System Initializing ---");
}

void loop() {
  if (!isPaired) {
    handlePairing(); // Waits for BLE pairing if not yet connected
  } else {
    monitorHeartbeat(); // Once paired WiFi is maintained and monitored with heartbeat
  }
}
