#include <WiFiUdp.h>

extern WiFiUDP udp;
extern const String MASTER_KEY;
extern const String BASE_ID;
extern const String DEVICE_NAME;

void handleIncomingUDP(String rawData, IPAddress senderIP, int senderPort) {
  // 1. Check if this is a Discovery Broadcast
  if (rawData == "DISCOVER_REQ") {
    sendDiscoveryReply(senderIP, senderPort);
    return;
  }

  // 2. Otherwise, treat as an Encrypted Command
  processIncomingCommand(rawData); 
}

void sendDiscoveryReply(IPAddress ip, int port) {
  // Construct Status String: Name|IP|Node1,Node2,Node3
  String status = getStatusString(); 
  String reply = DEVICE_NAME + "|" + WiFi.localIP().toString() + "|" + status;
  
  udp.beginPacket(ip, port);
  udp.print(reply);
  udp.endPacket();
  Serial.println("Discovery reply sent.");
}

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
