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
    String cmdID = doc["Command_ID"] | "0";
    String targetNode = doc["node"] | "";
    String val = doc["value"] | "low";
    
    executeCommand(targetNode, val);
    sendCommandResponse(cmdID, senderIP, senderPort);
  }
}
// DISCOVERY RESPONSE (ESP -> PI)
void sendDiscoveryResponse(IPAddress ip, int port) {
  StaticJsonDocument<512> doc;
  doc["device_name"] = BASE_NAME;
  doc["ip"] = WiFi.localIP().toString();
  doc["action"] = "discovery_response";
  
  JsonObject nodeL = doc.createNestedObject("Node_L");
  nodeL["attached"] = isNodeAttached(0);
  nodeL["power"] = isNodeOn(0);
  
  JsonObject nodeR = doc.createNestedObject("Node_R");
  nodeR["attached"] = isNodeAttached(1);
  nodeR["power"] = isNodeOn(1);

  JsonObject nodeNone = doc.createNestedObject("Node_C");
  nodeNone["attached"] = true;
  nodeNone["power"] = isNodeOn(2);

  sendJsonPacket(doc, ip, port);
}

// COMMAND RESPONSE (ESP -> PI)
void sendCommandResponse(String cmdID, IPAddress ip, int port) {
  StaticJsonDocument<256> doc;
  doc["Command_ID"] = cmdID;
  doc["base_name"] = BASE_NAME;
  doc["base_ip"] = WiFi.localIP().toString();
  doc["status"] = "success";
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
