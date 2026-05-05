#include <ArduinoJson.h>
#include <time.h>
#include <mbedtls/aes.h>
#include <mbedtls/sha256.h>
#include <esp_system.h>

const char* PASSKEY = "teamsocket";

// --- Externs ---
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

// --- Teammate's Crypto Helpers ---
void getKey(uint8_t key[16]) {
  uint8_t hash[32];
  mbedtls_sha256_context ctx;
  mbedtls_sha256_init(&ctx);
  mbedtls_sha256_starts(&ctx, 0);
  mbedtls_sha256_update(&ctx, (const uint8_t*)PASSKEY, strlen(PASSKEY));
  mbedtls_sha256_finish(&ctx, hash);
  mbedtls_sha256_free(&ctx);
  memcpy(key, hash, 16);
}

int addPadding(uint8_t* output, const uint8_t* input, int len) {
  int padLen = 16 - (len % 16);
  memcpy(output, input, len);
  for (int i = 0; i < padLen; i++) output[len + i] = padLen;
  return len + padLen;
}

int removePadding(uint8_t* data, int len) {
  int padLen = data[len - 1];
  if (padLen < 1 || padLen > 16) return -1;
  return len - padLen;
}

int encryptPacket(const uint8_t* plain, int plainLen, uint8_t* outPacket) {
  uint8_t key[16], iv[16];
  getKey(key);
  esp_fill_random(iv, 16);
  memcpy(outPacket, iv, 16);
  uint8_t padded[512];
  int paddedLen = addPadding(padded, plain, plainLen);
  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  mbedtls_aes_setkey_enc(&aes, key, 128);
  uint8_t ivCopy[16];
  memcpy(ivCopy, iv, 16);
  mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_ENCRYPT, paddedLen, ivCopy, padded, outPacket + 16);
  mbedtls_aes_free(&aes);
  return 16 + paddedLen;
}

int decryptPacket(const uint8_t* packet, int packetLen, uint8_t* outPlain) {
  if (packetLen < 32) return -1;
  uint8_t key[16], iv[16];
  getKey(key);
  memcpy(iv, packet, 16);
  int cipherLen = packetLen - 16;
  mbedtls_aes_context aes;
  mbedtls_aes_init(&aes);
  mbedtls_aes_setkey_dec(&aes, key, 128);
  mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_DECRYPT, cipherLen, iv, packet + 16, outPlain);
  mbedtls_aes_free(&aes);
  int plainLen = removePadding(outPlain, cipherLen);
  if (plainLen < 0) return -2;
  outPlain[plainLen] = '\0';
  return plainLen;
}

// --- Incoming Packet Handling ---
void processIncomingUDP(uint8_t* rawData, int len, IPAddress senderIP, int senderPort) {
  uint8_t decrypted[512];
  int plainLen = decryptPacket(rawData, len, decrypted);
  
  if (plainLen < 0) {
    Serial.println("[RX] Decryption Failed!");
    return;
  }

  Serial.println("[RX] Decrypted: " + String((char*)decrypted));
  
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, (char*)decrypted)) return; 

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

// --- Response Functions ---
void sendDiscoveryResponse(IPAddress ip, int port) {
  StaticJsonDocument<512> doc;
  doc["base"] = BASE_NAME;
  doc["action"] = "discovery_response";
  doc["base_power"] = isNodeOn(2);
  
  JsonObject node_l = doc.createNestedObject("node_l");
  node_l["attached"] = isNodeAttached(0);
  node_l["power"] = isNodeOn(0);
  
  JsonObject node_r = doc.createNestedObject("node_r");
  node_r["attached"] = isNodeAttached(1);
  node_r["power"] = isNodeOn(1);

  sendJsonPacket(doc, ip, port, "discovery_response");
}

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
  char jsonBuffer[512];
  serializeJson(doc, jsonBuffer);
  
  uint8_t encrypted[512];
  int encLen = encryptPacket((uint8_t*)jsonBuffer, strlen(jsonBuffer), encrypted);

  udp.beginPacket(ip, port);
  udp.write(encrypted, encLen);
  udp.endPacket();
  Serial.println("[TX] Sent Encrypted (" + label + ")");
}
