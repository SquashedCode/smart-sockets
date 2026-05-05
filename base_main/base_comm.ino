#include <ArduinoJson.h>
#include <time.h>

extern WiFiUDP udp;
extern void executeCommand(String node, String value);
extern void updateLEDStatus(String status);
extern void sendCommandResponse(String cmdID, String targetNode, String val, IPAddress ip, int port);
extern const String BASE_NAME;
extern IPAddress hubIP;
extern bool isDiscovered;
extern String pairedHubName;
extern bool isNodeAttached(int index);
extern bool isNodeOn(int index);

void processIncomingUDP(char* rawData, IPAddress senderIP, int senderPort) {
  Serial.println("[RX] PACKET RECEIVED");
  Serial.println("[RX] From: " + senderIP.toString() + ":" + String(senderPort));
  Serial.println("[RX] Content: " + String(rawData));
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, rawData)) return; 

  String action = doc["action"] | "";
  String hubName = doc["hub_name"] | "";

  if (action == "discovery") {
    if (!isDiscovered) {
      isDiscovered = true;
      isShutdown = false;
      pairedHubName = hubName;
      hubIP = senderIP;
      lastDiscoveryReceived = millis();
      
      updateLEDStatus("PAIRED");
      sendDiscoveryResponse(senderIP, senderPort);
    } 
    else if (hubName == pairedHubName) {
      lastDiscoveryReceived = millis();
    }
  }
  else if (isDiscovered && !isShutdown && action == "power") {
    String cmdID = doc["command_id"] | "0";
    String targetNode = doc["node"] | "";
    String val = doc["value"] | "low";
    
    executeCommand(targetNode, val);
    sendCommandResponse(cmdID, targetNode, val, senderIP, senderPort);
  }
}

void sendDiscoveryResponse(IPAddress ip, int port) {
  StaticJsonDocument<512> doc;
  doc["base"] = BASE_NAME;
  doc["ip"] = WiFi.localIP().toString();
  doc["action"] = "discovery_response";
  
  doc["base_power"] = isNodeOn(2);
  // Node_L
  JsonObject node_l = doc.createNestedObject("node_l");
  node_l["attached"] = isNodeAttached(0); // Boolean
  node_l["power"] = isNodeOn(0);         // Boolean
  
  // Node_R
  JsonObject node_r = doc.createNestedObject("node_r");
  node_r["attached"] = isNodeAttached(1); // Boolean
  node_r["power"] = isNodeOn(1);         // Boolean

  sendJsonPacket(doc, ip, port, "discovery_response");
}

// COMMAND RESPONSE
void sendCommandResponse(String cmdID, String targetNode, String val, IPAddress ip, int port) {
  StaticJsonDocument<512> doc;
  doc["action"] = "command_response";
  doc["command_id"] = cmdID;
  doc["base"] = BASE_NAME;
  doc["node"] = targetNode;
  doc["value"] = val;
  doc["status"] = "success"; 
  
  sendJsonPacket(doc, ip, port, "command_response");
}

void sendJsonPacket(JsonDocument& doc, IPAddress ip, int port, String label) {
  char buffer[512];
  serializeJson(doc, buffer);
  Serial.println("[TX] SENDING PACKET");
  Serial.println("[TX] Type: " + label);
  Serial.println("[TX] To: " + ip.toString() + ":" + String(port));
  Serial.println("[TX] Content: " + String(buffer));
  udp.beginPacket(ip, port);
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
}
