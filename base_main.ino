#include <WiFi.h>

// Global System States
const String LOCK_CODE = "87654321"; // Predetermined "Key" for each Base
bool isPaired = false;
String receivedSsid = "";
String receivedPass = "";

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
    handlePairing(); // Pairing
  } else {
    monitorHeartbeat(); // Wireless Connection Maintenance
  }
}