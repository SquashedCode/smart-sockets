#include <ArduinoJson.h>

extern WiFiUDP udp;
extern String getFormattedTime();
extern void executeCommand(String node, String value);
extern const String BASE_NAME;
extern unsigned long lastPacketReceived;
extern bool isShutdown;

// ESP-to-PI Heartbeat
void sendHeartbeat() {
  StaticJsonDocument<256> doc;
  doc["device_name"] = BASE_NAME;
  doc["ip"] = WiFi.localIP().toString();
  doc["Action"] = "Heartbeat";
  
  char buffer[256];
  serializeJson(doc, buffer);
  udp.beginPacket(udp.remoteIP(), UDP_PORT); // Hub IP
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
}

// Pi-to-ESP Heartbeat Response
void sendHeartbeatResponse(IPAddress ip, int port) {
  StaticJsonDocument<256> doc;
  doc["hub_name"] = "Hub_1";
  doc["ip"] = WiFi.localIP().toString();
  doc["Action"] = "Heartbeat_response";
  
  char buffer[256];
  serializeJson(doc, buffer);
  udp.beginPacket(ip, port);
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
}

// Command Response
void sendResponse(String cmdID, IPAddress ip, int port) {
  StaticJsonDocument<256> doc;
  doc["Command_ID"] = cmdID;         
  doc["base_name"] = BASE_NAME;      
  doc["base_ip"] = WiFi.localIP().toString();
  doc["status"] = "Success";
  doc["time"] = getFormattedTime();  
  
  char buffer[256];
  serializeJson(doc, buffer);
  udp.beginPacket(ip, port);
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
}

void handleIncomingUDP(char* jsonPayload, IPAddress senderIP, int senderPort) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, jsonPayload)) return; //

  String action = doc["Action"] | "";

  if (action == "Heartbeat") {
    lastPacketReceived = millis();
    if (isShutdown) isShutdown = false; //
    sendHeartbeatResponse(senderIP, senderPort);
  } 
  else if (action == "Power") {
    String cmdID = doc["Command_ID"];
    String node = doc["Node"]; //
    String value = doc["Value"];
    
    executeCommand(node, value);
    sendResponse(cmdID, senderIP, senderPort);
  }
}
