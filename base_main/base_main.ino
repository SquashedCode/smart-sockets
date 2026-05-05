#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <time.h>

const String BASE_NAME = "base_1";
const int UDP_PORT = 50000;
IPAddress hubIP;

bool isDiscovered = false;
bool isShutdown = false;
bool isUpdating = false;      // Added for firmware update state
String pairedHubName = ""; 
unsigned long lastDiscoveryReceived = millis();
unsigned long lastHeartbeatSent = 0;

WiFiUDP udp;

extern void setupPins();
extern void broadcastDiscovery();
extern void processIncomingUDP(char* rawData, IPAddress senderIP, int senderPort);
extern void sendHeartbeat();
extern void triggerTotalShutdown();
extern void updateLEDStatus(String status);

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- Base Station Booting ---");
  
  setupPins(); 
  
  WiFi.begin("CrimsonTraveler-2.4", "3CrimsonCrows!"); // [UPDATE YOUR CREDS]
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) { 
    delay(500); 
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected! IP: " + WiFi.localIP().toString());
  
  udp.begin(UDP_PORT);
  configTime(0, 0, "pool.ntp.org");

  Serial.println("--- SYSTEM IDLE: WAITING FOR DISCOVERY ---"); 
}

void loop() {
  if (isUpdating) {
    updateLEDStatus("UPDATING");
  }
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char incoming[512];
    int len = udp.read(incoming, 511);
    incoming[len] = '\0';
    processIncomingUDP(incoming, udp.remoteIP(), udp.remotePort());
  }

  if (isDiscovered && !isUpdating) {
    if (millis() - lastDiscoveryReceived > 16000) {
      Serial.println("!!SAFE MODE!!");
      isDiscovered = false;
      isShutdown = true;
      triggerTotalShutdown();
      updateLEDStatus("SAFE_MODE");
    }
  }
}
