#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
// Handles initial pairing and maintaining wireless connection 
unsigned long lastHeartbeat = 0;
const unsigned long heartbeatInterval = 3000;

class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      String value = pCharacteristic->getValue().c_str();
      if (value.length() > 0) {
        int separator = value.indexOf(':');
        receivedSsid = value.substring(0, separator);
        receivedPass = value.substring(separator + 1);
        // We set isPaired later in handlePairing only after WiFi is solid
      }
    }
};

void handlePairing() {
  BLEDevice::init(LOCK_CODE.c_str());
  BLEServer *pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService("4fafc201-1fb5-459e-8fcc-c5c9c331914b");
  BLECharacteristic *pChar = pService->createCharacteristic("beb5483e-36e1-4688-b7f5-ea07361b26a8", BLECharacteristic::PROPERTY_WRITE);
  
  pChar->setCallbacks(new MyCallbacks());
  pService->start();
  pServer->getAdvertising()->start();

  Serial.println("Waiting for Hub credentials...");
  while (receivedSsid == "") { delay(100); }
  
  Serial.println("Credentials Received! Beginning WiFi connection");
  pServer->getAdvertising()->stop();
  BLEDevice::deinit(true);
  
  WiFi.mode(WIFI_OFF);
  delay(1000);
  WiFi.mode(WIFI_STA);
  WiFi.begin(receivedSsid.c_str(), receivedPass.c_str());

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  isPaired = true; 
  lastHeartbeat = millis(); // Initialize Safe Mode timer only after connection
  Serial.println("\nWiFi Connected! Heartbeat active.");
}

void monitorHeartbeat() {
  if (!isPaired || WiFi.status() != WL_CONNECTED) return;

  // Safe Mode check every 6 seconds
  if (millis() - lastHeartbeat > 6000) {
    Serial.println("!!! SYSTEM BLACKOUT !!! Heartbeat Lost.");
    triggerTotalShutdown(); 
    return;
  }

  if (millis() - lastHeartbeat > heartbeatInterval) {
    WiFiClient client;
    if (client.connect("192.168.1.65", 5000)) {
      client.println("STATUS_OK_" + LOCK_CODE);
      
      unsigned long start = millis();
      while (client.available() == 0 && millis() - start < 500) { delay(10); }
      
      if (client.available() > 0) {
        String command = client.readStringUntil('\n');
        executeCommand(command); 
      }
      lastHeartbeat = millis(); 
    }
  }
}