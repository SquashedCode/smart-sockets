#include <WiFi.h>
#include <WiFiUdp.h>

const String BASE_ID = "BASE_001"; 
const String DEVICE_NAME = "Living Room";
const String MASTER_KEY = "SECRET_1234";
const int UDP_PORT = 50000;

WiFiUDP udp;
bool isShutdown = false; 
unsigned long lastPacketReceived = millis(); // Track time

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  setupPins(); 
  
  WiFi.begin("CrimsonTraveler-2.4", "3CrimsonCrows!");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  
  udp.begin(UDP_PORT);
  Serial.println("\n--- Initialized: " + DEVICE_NAME + " ---");
}

void loop() {
  // 1. Always listen for packets (even if shutdown)
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char incoming[512];
    int len = udp.read(incoming, 511);
    incoming[len] = '\0';
    handleIncomingUDP(incoming, udp.remoteIP(), udp.remotePort());
  }

  // 2. FR3 Requirement: Safe Mode Watchdog (6 Seconds)
  if (!isShutdown && (millis() - lastPacketReceived > 6000)) {
    Serial.println("Heartbeat lost! Activating Safe Mode.");
    triggerTotalShutdown();
    isShutdown = true;
  }
  
  delay(10);
}
