#include <WiFi.h>
#include <ArduinoOTA.h>

// Global System States
const String LOCK_CODE = "87654321";
bool isPaired = false;
bool isShutdown = false; 

String receivedSsid = ""; 
String receivedPass = ""; 

// Functions
void startPairing();          // NEW: Non-blocking BLE setup
void connectToWiFi();         // NEW: Logic to switch from BLE to WiFi
void monitorHeartbeat();     
void executeCommand(String cmd); 
void setupPins();            
void triggerTotalShutdown();

void setup() {
  Serial.begin(115200);
  delay(1000); 
  setupPins(); 
  startPairing(); // Start advertising once and return immediately
  Serial.println("--- System Initializing ---");
}

void setupOTA() {
  ArduinoOTA.setHostname("SocketBase-01");
  ArduinoOTA.setPassword("your_secure_password"); // Recommended for security

  ArduinoOTA.onStart([]() { Serial.println("OTA Update Starting..."); });
  ArduinoOTA.onEnd([]() { Serial.println("OTA Update Finished. Rebooting."); });
  
  ArduinoOTA.begin();
  Serial.println("OTA Service Initialized.");
}

void loop() {
  if (isShutdown) {
    delay(100); 
    return;
  }

  // State Machine: If not paired but credentials arrived via BLE, connect to WiFi
  if (!isPaired && receivedSsid != "") {
    connectToWiFi();
  } 
  else if (isPaired) {
    ArduinoOTA.handle();
    monitorHeartbeat();
  }
  
  delay(10); 
}
