// base_commands.ino
extern bool isShutdown; 

const int BASE_LED = 4; // Status LED updated to Pin 4
const int NUM_NODES = 3; 

// Placeholder pins - UPDATE THESE once hardware is decided
// Use safe pins for ESP32-C3 (e.g., 5, 6, 7)
const int NODE_PINS[NUM_NODES] = {0, 0, 0}; 

void setupPins() {
  pinMode(BASE_LED, OUTPUT);
  digitalWrite(BASE_LED, LOW);
  
  for (int i = 0; i < NUM_NODES; i++) {
    pinMode(NODE_PINS[i], OUTPUT);
    digitalWrite(NODE_PINS[i], LOW);
  }
  Serial.println("3-Node GPIO Initialized on C3-Safe Pins.");
}

void triggerTotalShutdown() {
  Serial.println("Connection lost, activating Safe Mode.");
  digitalWrite(BASE_LED, LOW);
  for (int i = 0; i < NUM_NODES; i++) {
    digitalWrite(NODE_PINS[i], LOW);
  }
  isShutdown = true; 
}

void executeCommand(String cmd) {
  if (isShutdown) return;

  Serial.println("Processing: " + cmd);

  if (cmd.indexOf("BASE 87654321 OFF") >= 0) {
    triggerTotalShutdown();
    return;
  }

  // Handle nodes 1 to 3
  for (int i = 1; i <= NUM_NODES; i++) {
    String nodeTarget = "NODE " + String(i);
    if (cmd.indexOf(nodeTarget + " ON") >= 0) {
      digitalWrite(NODE_PINS[i-1], HIGH);
      Serial.println(nodeTarget + " set to ON");
    } 
    else if (cmd.indexOf(nodeTarget + " OFF") >= 0) {
      digitalWrite(NODE_PINS[i-1], LOW);
      Serial.println(nodeTarget + " set to OFF");
    }
  }

  if (cmd.indexOf("BASE 87654321 ON") >= 0) {
    digitalWrite(BASE_LED, HIGH);
    for (int i = 0; i < NUM_NODES; i++) {
      digitalWrite(NODE_PINS[i], HIGH);
    }
    Serial.println("Global ON command executed.");
  }
}
