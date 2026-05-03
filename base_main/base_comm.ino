#include <WiFiUdp.h>

extern WiFiUDP udp;
extern const String MASTER_KEY;
extern const String BASE_ID;
extern const String DEVICE_NAME;
extern unsigned long lastPacketReceived;
extern bool isShutdown;

void handleIncomingUDP(String rawData, IPAddress senderIP, int senderPort) {
  // 1. Discovery Packet
  if (rawData == "DISCOVER_REQ") {
    sendDiscoveryReply(senderIP, senderPort);
    return;
  }

  // 2. Heartbeat Packet Format: "HubName,HubIP,Heartbeat"
  if (rawData.indexOf("Heartbeat") >= 0) {
    processHeartbeat(rawData, senderIP, senderPort);
    return;
  }

  // 3. Encrypted Command
  processIncomingCommand(rawData); 
}

void processHeartbeat(String packet, IPAddress senderIP, int senderPort) {
  // Reset Watchdog Timer
  lastPacketReceived = millis();
  
  // Recover from Safe Mode if we were shut down
  if (isShutdown) {
    Serial.println("Heartbeat received. Recovery initiated (System OFF).");
    isShutdown = false;
    // Note: Per requirement, system stays OFF/Safe until new commands arrive
  }

  // Reply: "BaseName,HubIP,Heartbeat"
  String reply = DEVICE_NAME + "," + WiFi.localIP().toString() + ",Heartbeat";
  udp.beginPacket(senderIP, senderPort);
  udp.print(reply);
  udp.endPacket();
}

void sendDiscoveryReply(IPAddress ip, int port) {
  String status = getStatusString(); 
  String reply = DEVICE_NAME + "|" + WiFi.localIP().toString() + "|" + status;
  udp.beginPacket(ip, port);
  udp.print(reply);
  udp.endPacket();
}

// Keep your existing decryptXOR and processIncomingCommand logic...

// Reuse your decryption logic from before
String decryptXOR(String data, String key) { /* ... keep your existing logic ... */ }

void processIncomingCommand(String rawData) {
  String decrypted = decryptXOR(rawData, MASTER_KEY);
  int colonIndex = decrypted.indexOf(':');
  if (colonIndex == -1) return;
  
  if (decrypted.substring(0, colonIndex) == BASE_ID) {
    executeCommand(decrypted.substring(colonIndex + 1));
  }
}
