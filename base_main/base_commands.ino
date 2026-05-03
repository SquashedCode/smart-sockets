#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <time.h>

const String BASE_NAME = "Base_1";
const int UDP_PORT = 50000;
unsigned long lastPacketReceived = millis();
unsigned long lastHeartbeatSent = 0; 
bool isShutdown = false;

WiFiUDP udp;

void setup() {
  Serial.begin(115200);
  setupPins(); 
  
  WiFi.begin("CrimsonTraveler-2.4", "3CrimsonCrows!");
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  
  configTime(0, 0, "pool.ntp.org");
  udp.begin(UDP_PORT);
}

void loop() {
  // Receive UDP
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char incoming[512];
    int len = udp.read(incoming, 511);
    incoming[len] = '\0';
    handleIncomingUDP(incoming, udp.remoteIP(), udp.remotePort());
  }

  // Periodic ESP-to-PI Heartbeat
  if (millis() - lastHeartbeatSent > 3000) {
    sendHeartbeat();
    lastHeartbeatSent = millis();
  }

  // FR3: Safe Mode Timeout (6s)
  if (!isShutdown && (millis() - lastPacketReceived > 6000)) {
    Serial.println("Heartbeat lost. Safe Mode engaged.");
    triggerTotalShutdown(); //
    isShutdown = true;
  }
}
