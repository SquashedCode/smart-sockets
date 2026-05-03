#include <ArduinoJson.h>

// --- Externs ---
extern WiFiUDP udp;
extern String getFormattedTime();
extern void executeCommand(String node, String value);
extern const String BASE_NAME;
extern unsigned long lastPacketReceived;
extern bool isShutdown;

// DEFINITIONS FIRST 

// Responding to Hub Heartbeat
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

// Responding to Command Packet (Base -> Hub)
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

// NOW CALL THEM

void handleIncomingUDP(char* jsonPayload, IPAddress senderIP, int senderPort) {
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, jsonPayload);

  if (error) {
    Serial.println("Failed to parse JSON packet.");
    return;
  }

  String action = doc["Action"] | "";

  // Handle Heartbeat (FR3 Requirement)
  if (action == "Heartbeat") {
    lastPacketReceived = millis();
    if (isShutdown) isShutdown = false;
    sendHeartbeatResponse(senderIP, senderPort);
  } 
  // Handle Power Commands (FR10 Requirement)
  else if (action == "Power") {
    String cmdID = doc["Command_ID"];
    String node = doc["Node"];
    String value = doc["Value"];
    
    executeCommand(node, value);
    sendResponse(cmdID, senderIP, senderPort);
  }
}
