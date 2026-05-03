#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <time.h>

const String BASE_NAME = "Base_1";
const int UDP_PORT = 50000;
unsigned long lastPacketReceived = millis();
bool isShutdown = false;

WiFiUDP udp;

void setup() {
  Serial.begin(115200);
  setupPins(); // From base_commands
  
  WiFi.begin("CrimsonTraveler-2.4", "3CrimsonCrows!");
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  
  // Initialize NTP for accurate timestamps
  configTime(0, 0, "pool.ntp.org"); 
  
  udp.begin(UDP_PORT);
}

// 
String getFormattedTime() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "0-0-0-0:0:0";
  char buffer[32];
  strftime(buffer, sizeof(buffer), "%m-%d-%y-%H:%M:%S", &timeinfo);
  return String(buffer);
}

void loop() {
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char incoming[512];
    int len = udp.read(incoming, 511);
    incoming[len] = '\0';
    handleIncomingUDP(incoming, udp.remoteIP(), udp.remotePort());
  }

  // FR3: Safe Mode Timeout (6s)
  if (!isShutdown && (millis() - lastPacketReceived > 6000)) {
    Serial.println("Heartbeat lost. Safe Mode engaged.");
    triggerTotalShutdown();
    isShutdown = true;
  }
}
