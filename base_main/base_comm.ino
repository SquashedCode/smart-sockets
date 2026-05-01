#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <WiFi.h>

extern bool isPaired;
extern bool isShutdown;
extern String receivedSsid;
extern String receivedPass;
extern const String LOCK_CODE;

unsigned long lastHeartbeat = 0;
const unsigned long heartbeatInterval = 3000;

class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue().c_str();
      if (value.length() > 0) {
        int separator = value.indexOf(':');
        if (separator > 0) {
          receivedSsid = value.substring(0, separator);
          receivedPass = value.substring(separator + 1);
          Serial.println("Credentials received via BLE!");
        }
      }
    }
};

void startPairing() {
  BLEDevice::init(LOCK_CODE.c_str());
  BLEServer *pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService("4fafc201-1fb5-459e-8fcc-c5c9c331914b");
  BLECharacteristic *pChar = pService->createCharacteristic("beb5483e-36e1-4688-b7f5-ea07361b26a8", BLECharacteristic::PROPERTY_WRITE);
  
  pChar->setCallbacks(new MyCallbacks());
  pService->start();
  pServer->getAdvertising()->start();
  Serial.println("Advertising 8-digit code: " + LOCK_CODE);
}

void connectToWiFi() {
  Serial.println("Credentials Received! Connecting to WiFi...");
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(receivedSsid.c_str(), receivedPass.c_str());

  // Non-blocking wait for connection (uses timeout check instead of loop)
  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - startAttempt < 15000)) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    isPaired = true;
    lastHeartbeat = millis();
    Serial.println("\nWiFi Connected! Heartbeat active.");
  } else {
    Serial.println("\nWiFi connection failed. Clearing credentials to retry.");
    receivedSsid = ""; // Reset to allow retry from BLE
  }
}

void monitorHeartbeat() {
  if (isShutdown || !isPaired || WiFi.status() != WL_CONNECTED) return;

  if (millis() - lastHeartbeat > 6000) {
    triggerTotalShutdown();
    return;
  }

  if (millis() - lastHeartbeat > heartbeatInterval) {
    WiFiClient client;
    if (client.connect("192.168.1.65", 5000)) {
      client.println("STATUS_OK_" + LOCK_CODE);
      lastHeartbeat = millis();
      
      // Read command if available
      if (client.available() > 0) {
        String command = client.readStringUntil('\n');
        executeCommand(command);
      }
    }
  }
}
