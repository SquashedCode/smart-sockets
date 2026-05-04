#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <time.h>

// --- Configuration ---
const String BASE_NAME = "Base_1";
const int UDP_PORT = 50000;
IPAddress hubIP;

// --- System State Variables ---
bool isDiscovered = false;
bool isShutdown = false;
bool isUpdating = false;      // Added for firmware update state
String pairedHubName = ""; 
unsigned long lastHeartbeatReceived = millis();
unsigned long lastHeartbeatSent = 0;

WiFiUDP udp;

// --- Extern Declarations (Linking to base_comm & base_commands) ---
extern void setupPins();
extern void broadcastDiscovery();
extern void processIncomingUDP(char* rawData, IPAddress senderIP, int senderPort);
extern void sendHeartbeat();
extern void triggerTotalShutdown();
extern void updateLEDStatus(String status);

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- Base Station Booting ---");
  
  // Initialize Relays and LEDs (LED defaults to IDLE/White)
  setupPins(); 
  
  // WiFi Connection
  WiFi.begin("CrimsonTraveler-2.4", "3CrimsonCrows!"); // [UPDATE YOUR CREDS]
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) { 
    delay(500); 
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected! IP: " + WiFi.localIP().toString());
  
  // Network Initialization
  udp.begin(UDP_PORT);
  configTime(0, 0, "pool.ntp.org");

  Serial.println("--- SYSTEM IDLE: WAITING FOR DISCOVERY ---");
  Serial.println("The Base is waiting for a UDP packet containing the following JSON:");
  Serial.println("{\"Action\": \"discovery\", \"Hub_Name\": \"YOUR_HUB_NAME_HERE\"}");  
}

void loop() {
  // 1. LED State Management for Firmware Updates
  if (isUpdating) {
    updateLEDStatus("UPDATING");
  }

  // 2. UDP Packet Handling
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char incoming[512];
    int len = udp.read(incoming, 511);
    incoming[len] = '\0';
    processIncomingUDP(incoming, udp.remoteIP(), udp.remotePort());
  }

  // 3. Operational Logic (Only if successfully paired with Hub)
  if (isDiscovered && !isUpdating) {
    
    // Heartbeat Protocol: Send every 6 seconds
    if (millis() - lastHeartbeatSent > 6000) {
      sendHeartbeat();
      lastHeartbeatSent = millis();
    }

    // Safe Mode Protocol: Trigger if no response for 10s
    if (!isShutdown && (millis() - lastHeartbeatReceived > 10000)) {
      Serial.println("!! Safe Mode!!: No heartbeat response for 10s. Entering Safe Mode !!");
      triggerTotalShutdown(); // Sets LEDs to SAFE_MODE (Yellow)
      isShutdown = true;
    }
  }
}
