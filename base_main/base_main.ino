#include <WiFi.h>
#include <ArduinoOTA.h>

// --- NFR4: Cluster Identity ---
const String BASE_ID = "BASE_001"; 

const String MASTER_KEY = "SECRET_1234"; // Must match the Hub's key

// Global System States
const String LOCK_CODE = "87654321";
bool isPaired = false;
bool isShutdown = false; 
String receivedSsid = ""; 
String receivedPass = ""; 

// --- NFR2: Decryption Logic ---
String decryptXOR(String data, String key) {
  String output = "";
  for (int i = 0; i < data.length(); i++) {
    output += (char)(data[i] ^ key[i % key.length()]);
  }
  return output;
}


void processIncomingCommand(String rawData) {
  String decrypted = decryptXOR(rawData, MASTER_KEY);
  
  int colonIndex = decrypted.indexOf(':');
  if (colonIndex == -1) {
    Serial.println("Invalid packet format.");
    return;
  }
  
  String incomingID = decrypted.substring(0, colonIndex);
  String command = decrypted.substring(colonIndex + 1);
  
  if (incomingID != BASE_ID) {
    Serial.println("Ignored: Targeted at different cluster.");
    return;
  }
  
  executeCommand(command);
}

// Functions
void startPairing();          
void connectToWiFi();         
void monitorHeartbeat();     
void executeCommand(String cmd); 
void setupPins();            
void triggerTotalShutdown();

void setup() {
  Serial.begin(115200);
  delay(1000); 
  setupPins(); 
  
  Serial.print("--- System Initializing: ");
  Serial.print(BASE_ID);
  Serial.println(" ---");
  
  startPairing(); 
}

void loop() {
  if (isShutdown) {
    delay(100); 
    return;
  }

  if (!isPaired && receivedSsid != "") {
    connectToWiFi();
  } 
  else if (isPaired) {
    ArduinoOTA.handle();
    monitorHeartbeat();

  }
  delay(10); 
}
