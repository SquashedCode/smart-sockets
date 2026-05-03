#include <ArduinoJson.h>
#include <time.h>

// --- Extern Declarations ---
extern WiFiUDP udp;
extern void executeCommand(String node, String value);
extern void updateLEDStatus(String status);
extern void sendCommandResponse(String cmdID, IPAddress ip, int port);
extern const String BASE_NAME;
extern IPAddress hubIP;
extern bool isDiscovered;
extern bool isShutdown;
extern String pairedHubName;
extern unsigned long lastHeartbeatReceived;
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

// --- Discovery Response (Matches your requested JSON format) ---
void processIncomingUDP(char* rawData, IPAddress senderIP, int senderPort) {
  // Always log incoming data
  Serial.println("RX Raw: " + String(rawData));
  
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, rawData)) {
    Serial.println("Error: Received packet is not valid JSON.");
    return;
  }

  String action = doc["Action"] | "";
  String hubName = doc["Hub_Name"] | "";

  // 1. Discovery Phase
  if (action == "discovery") {
    if (hubName != "") {
      isDiscovered = true;
      pairedHubName = hubName;
      Serial.println("SUCCESS: Discovery confirmed. Paired with: " + hubName);
      updateLEDStatus("PAIRED");
      sendDiscoveryResponse(senderIP, senderPort);
    } else {
      Serial.println("Error: 'Action' was Discovery, but 'Hub_Name' was missing or empty.");
    }
  } 
  else {
    // If we aren't discovered and the packet wasn't the correct Discovery packet
    if (!isDiscovered) {
      Serial.println("Status: Still waiting for Discovery. Packet ignored.");
    }
  }

  // 2. Operational Logic
  if (isDiscovered && hubName == pairedHubName) {
    if (action == "Heartbeat_response") {
      lastHeartbeatReceived = millis();
      isShutdown = false;
      Serial.println("Heartbeat_response received.");
    }
    else if (action == "Power") {
      String cmdID = doc["Command_ID"].as<String>();
      String target = doc["Node"].as<String>(); 
      if (target == "" || target == "NONE") target = doc["Base"].as<String>();
      
      executeCommand(target, doc["Value"].as<String>());
      sendCommandResponse(cmdID, senderIP, senderPort);
    }
  }
}

// Update this to use the passed IP and port
void sendDiscoveryResponse(IPAddress ip, int port) {
  StaticJsonDocument<512> doc;
  doc["device_name"] = BASE_NAME;
  doc["ip"] = WiFi.localIP().toString();
  doc["Action"] = "Discovery_Response";
  
  // Nested Node Status
  JsonObject nodeL = doc.createNestedObject("Node_L");
  nodeL["Attached"] = isNodeAttached(0);
  nodeL["Power"] = isNodeOn(0);
  
  JsonObject nodeR = doc.createNestedObject("Node_R");
  nodeR["Attached"] = isNodeAttached(1);
  nodeR["Power"] = isNodeOn(1);

  JsonObject nodeNone = doc.createNestedObject("NONE");
  nodeNone["Attached"] = false;
  nodeNone["Power"] = isNodeOn(2);

  char buffer[512];
  serializeJson(doc, buffer);
  Serial.println("TX [Discovery_Response]: " + String(buffer));
  
  udp.beginPacket(ip, port);
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
}

// --- Heartbeat Outbound ---
void sendHeartbeat() {
  StaticJsonDocument<256> doc;
  doc["device_name"] = BASE_NAME;
  doc["ip"] = WiFi.localIP().toString();
  doc["Action"] = "Heartbeat";
  
  char buffer[256];
  serializeJson(doc, buffer);
  
  // Send directly to the paired Hub IP instead of broadcast
  udp.beginPacket(hubIP, 50000); 
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
  
  Serial.println("TX [Heartbeat] to " + hubIP.toString() + ": " + String(buffer));
}

// --- Command Response ---
void sendCommandResponse(String cmdID, IPAddress ip, int port) {
  StaticJsonDocument<256> doc;
  doc["Command_ID"] = cmdID;
  doc["base_name"] = BASE_NAME;
  doc["base_ip"] = WiFi.localIP().toString();
  doc["status"] = "Success";
  doc["time"] = getFormattedTime();
  
  char buffer[256];
  serializeJson(doc, buffer);
  Serial.println("TX [Response]: " + String(buffer));
  
  udp.beginPacket(ip, port);
  udp.write((uint8_t*)buffer, strlen(buffer));
  udp.endPacket();
}
