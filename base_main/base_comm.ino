#include <ArduinoJson.h>
#include <time.h>

// --- Externs ---
extern WiFiUDP udp;
extern void executeCommand(String node, String value);
extern void updateLEDStatus(String status);
extern const String BASE_NAME;
extern IPAddress hubIP;
extern bool isDiscovered;
extern String pairedHubName;
extern bool isNodeAttached(int index);
extern bool isNodeOn(int index);

String getPowerStatus(bool isOn) {
  return isOn ? "on" : "off";
}
String getAttachmentStatus(bool isAttached) {
  return isAttached ? "attached" : "disconnected";
}

// --- Time Helper ---
String getFormattedTime() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "0-0-0-0:0:0";
  char buffer[32];
  strftime(buffer, sizeof(buffer), "%m-%d-%y-%H:%M:%S", &timeinfo);
  return String(buffer);
}

// --- Incoming Packet Handling ---
void processIncomingUDP(char* rawData, IPAddress senderIP, int senderPort) {
  Serial.println("--- NEW UDP PACKET RECEIVED ---");
  Serial.print("From IP: "); Serial.println(senderIP.toString());
  Serial.print("Raw Data: "); Serial.println(rawData);
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, rawData)) return; 

  String action = doc["action"] | "";
  String hubName = doc["hub_name"] | "";

  // 1. DISCOVERY LOGIC (Acts as both Pairing and Heartbeat)
  if (action == "discovery") {
    if (!isDiscovered) {
      isDiscovered = true;
      isShutdown = false; // Wake up from safe mode
      pairedHubName = hubName;
      hubIP = senderIP;
      lastDiscoveryReceived = millis(); // Reset timer
      
      Serial.println("SUCCESS: Paired with Hub: " + hubName);
      updateLEDStatus("PAIRED"); // Green
      sendDiscoveryResponse(senderIP, senderPort);
    } 
        else if (hubName == pairedHubName) {
      lastDiscoveryReceived = millis(); // Reset watchdog timer
      }
  }
  
  else if (isDiscovered && !isShutdown && action == "power") {
    String targetNode = doc["node"] | "";
    String val = doc["value"] | "low";
    
    executeCommand(targetNode, val);
    sendCommandResponse(senderIP, senderPort);
  }
}
// DISCOVERY RESPONSE (ESP -> PI)
void sendDiscoveryResponse(IPAddress ip, int port) {
  StaticJsonDocument<512> doc;
  doc["base"] = BASE_NAME;
  doc["ip"] = WiFi.localIP().toString();
  doc["action"] = "discovery_response"; // Ensure this key matches your Pi's expected key

  // Node_L
  JsonObject node_L = doc.createNestedObject("Node_L");
  node_L["attached"] = getAttachmentStatus(isNodeAttached(0));
  node_L["power"] = getPowerStatus(isNodeOn(0));
  
  // Node_R
  JsonObject node_R = doc.createNestedObject("Node_R");
  node_R["attached"] = getAttachmentStatus(isNodeAttached(1));
  node_R["power"] = getPowerStatus(isNodeOn(1));

  // Node_C
  JsonObject node_C = doc.createNestedObject("Node_C");
  node_C["power"] = getPowerStatus(isNodeOn(2));

  // Send the packet
  sendJsonPacket(doc, ip, port, "Discovery_Response");
}

// COMMAND RESPONSE (ESP -> PI)
void sendCommandResponse(IPAddress ip, int port) {
  StaticJsonDocument<256> doc;
  doc["base_name"] = BASE_NAME;
  doc["base_ip"] = WiFi.localIP().toString();
  doc["status"] = "success";
  doc["time"] = getFormattedTime();
  
  sendJsonPacket(doc, ip, port, "command_response");
}

// Helper to serialize and send
void sendJsonPacket(JsonDocument& doc, IPAddress ip, int port, String label) {
  char buffer[512];
  serializeJson(doc, buffer);
  udp.beginPacket(ip, port);
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
  Serial.println("Packet Type: " + label);
  Serial.println("Destination: " + ip.toString() + ":" + String(port));
  Serial.println("Payload: " + String(buffer));
}
