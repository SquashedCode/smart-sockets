#include <WiFi.h>
#include <WiFiUdp.h>

// --- System Configuration ---
const String BASE_ID = "BASE_001"; 
const String DEVICE_NAME = "Living Room";
const String MASTER_KEY = "SECRET_1234";
const int UDP_PORT = 50000;

WiFiUDP udp;
bool isShutdown = false; 

// --- Core Logic ---
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  setupPins(); // From base_commands
  
  // Hardcoded WiFi connection
  WiFi.begin("Crimson-traveler", "3CrimsonCrows!");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  
  udp.begin(UDP_PORT);
  Serial.println("\n--- Initialized: " + DEVICE_NAME + " ---");
}

void loop() {
  if (isShutdown) return;

  // Handle incoming UDP
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char incoming[512];
    int len = udp.read(incoming, 511);
    incoming[len] = '\0';
    
    // Pass to communication handler
    handleIncomingUDP(incoming, udp.remoteIP(), udp.remotePort());
  }
  delay(10);
}
