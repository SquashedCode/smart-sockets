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
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, rawData)) return; 

  String action = doc["Action"] | "";
  String hubName = doc["Hub_Name"] | doc["hub_name"] | ""; // Flexible key check

  // 1. DISCOVERY HANDSHAKE
  if (action == "discovery") {
    isDiscovered = true;
    pairedHubName = hubName;
    hubIP = senderIP; // Update Hub IP dynamically
    updateLEDStatus("PAIRED");
    sendDiscoveryResponse(senderIP, senderPort);
  }

  // 2. HEARTBEAT RESPONSE
  else if (action == "Heartbeat_response") {
    // Hub responded, connection is alive
    Serial.println("Heartbeat_response received from " + hubName);
  }

  // 3. COMMAND RECEIVED
else if (action == "Power") {
    String cmdID = doc["Command_ID"] | "0";
    String targetNode = doc["Node"] | "";
    String val = doc["Value"] | "Low";

    Serial.println("Command [" + cmdID + "] for " + targetNode + " set to " + val);
    // Execute hardware action
    executeCommand(targetNode, val);
    // Respond back to Hub
    sendCommandResponse(cmdID, senderIP, senderPort);
  }
}

// --- Outgoing Packet Schemas ---

// DISCOVERY RESPONSE (ESP -> PI)
void sendDiscoveryResponse(IPAddress ip, int port) {
  StaticJsonDocument<512> doc;
  doc["device_name"] = BASE_NAME;
  doc["ip"] = WiFi.localIP().toString();
  doc["Action"] = "Discovery_Response";
  
  JsonObject nodeL = doc.createNestedObject("Node_L");
  nodeL["Attached"] = isNodeAttached(0);
  nodeL["Power"] = isNodeOn(0);
  
  JsonObject nodeR = doc.createNestedObject("Node_R");
  nodeR["Attached"] = isNodeAttached(1);
  nodeR["Power"] = isNodeOn(1);

  JsonObject nodeNone = doc.createNestedObject("Node_C");
  nodeNone["Attached"] = false;
  nodeNone["Power"] = isNodeOn(2);

  sendJsonPacket(doc, ip, port);
}

// HEARTBEAT (ESP -> PI)
void sendHeartbeat() {
  StaticJsonDocument<256> doc;
  doc["device_name"] = BASE_NAME;
  doc["ip"] = WiFi.localIP().toString();
  doc["Action"] = "Heartbeat";
  
  sendJsonPacket(doc, hubIP, 50000);
}

// COMMAND RESPONSE (ESP -> PI)
void sendCommandResponse(String cmdID, IPAddress ip, int port) {
  StaticJsonDocument<256> doc;
  doc["Command_ID"] = cmdID;
  doc["base_name"] = BASE_NAME;
  doc["base_ip"] = WiFi.localIP().toString();
  doc["status"] = "Success";
  doc["time"] = getFormattedTime();
  
  sendJsonPacket(doc, ip, port);
}

// Helper to serialize and send
void sendJsonPacket(JsonDocument& doc, IPAddress ip, int port) {
  char buffer[512];
  serializeJson(doc, buffer);
  udp.beginPacket(ip, port);
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
  Serial.println("TX: " + String(buffer));
}
