#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const int UDP_PORT = 50000;

String device_name = "ESP Device";
String device_status = "online";

WiFiUDP udp;

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("Starting ESP32 UDP discovery responder...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi connected!");
  Serial.print("ESP IP address: ");
  Serial.println(WiFi.localIP());

  udp.begin(UDP_PORT);

  Serial.print("Listening on UDP port ");
  Serial.println(UDP_PORT);
}

void loop() {
  int packetSize = udp.parsePacket();

  if (packetSize > 0) {
    char incomingPacket[512];

    int len = udp.read(incomingPacket, sizeof(incomingPacket) - 1);
    incomingPacket[len] = '\0';

    IPAddress senderIP = udp.remoteIP();
    int senderPort = udp.remotePort();

    Serial.println();
    Serial.print("Packet received from ");
    Serial.print(senderIP);
    Serial.print(":");
    Serial.println(senderPort);

    Serial.print("Packet data: ");
    Serial.println(incomingPacket);

    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, incomingPacket);

    if (error) {
      Serial.println("Invalid JSON packet");
      return;
    }

    String type = doc["type"] | "";

    if (type == "DISCOVERY") {
      sendDiscoveryResponse(senderIP, senderPort);
    }

    else if (type == "PING") {
      sendPong(senderIP, senderPort);
    }

    else if (type == "RENAME") {
      String newName = doc["new_name"] | "";

      if (newName.length() > 0) {
        device_name = newName;
        Serial.print("Device renamed to: ");
        Serial.println(device_name);
      }

      sendStatus(senderIP, senderPort);
    }

    else if (type == "TogglePower") {
      String value = doc["value"] | "";

      if (value == "High") {
        device_status = "ON";
      } 
      else if (value == "Low") {
        device_status = "OFF";
      }

      sendStatus(senderIP, senderPort);
    }

    else {
      Serial.println("Unknown command type");
    }
  }
}

void sendDiscoveryResponse(IPAddress targetIP, int targetPort) {
  StaticJsonDocument<256> response;

  response["type"] = "DISCOVERY_RESPONSE";
  response["name"] = device_name;
  response["ip"] = WiFi.localIP().toString();
  response["status"] = device_status;
  response["device_type"] = "ESP32";
  response["port"] = UDP_PORT;

  sendJson(response, targetIP, targetPort);

  Serial.println("Discovery response sent");
}

void sendPong(IPAddress targetIP, int targetPort) {
  StaticJsonDocument<256> response;

  response["type"] = "PONG";
  response["name"] = device_name;
  response["ip"] = WiFi.localIP().toString();
  response["status"] = device_status;

  sendJson(response, targetIP, targetPort);

  Serial.println("PONG sent");
}

void sendStatus(IPAddress targetIP, int targetPort) {
  StaticJsonDocument<256> response;

  response["type"] = "STATUS";
  response["name"] = device_name;
  response["ip"] = WiFi.localIP().toString();
  response["status"] = device_status;

  sendJson(response, targetIP, targetPort);

  Serial.println("Status sent");
}

void sendJson(StaticJsonDocument<256>& doc, IPAddress targetIP, int targetPort) {
  char buffer[256];

  size_t len = serializeJson(doc, buffer);

  udp.beginPacket(targetIP, targetPort);
  udp.write((uint8_t*)buffer, len);
  udp.endPacket();

  Serial.print("Sent to ");
  Serial.print(targetIP);
  Serial.print(":");
  Serial.println(targetPort);
}
