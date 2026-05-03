// base_commands.ino - Hardware Driver Layer
// Handles GPIO configuration, Relay Actuation, and Status Reporting

const int BASE_LED = 4;           // Status LED on GPIO 4
const int NUM_NODES = 3;          // Total nodes per base
// Update these pin numbers to match your actual PCB schematic
const int NODE_PINS[NUM_NODES] = {2, 6, 7}; 

// Helper to safely trigger a total system shutdown (Safe Mode)
void triggerTotalShutdown() {
  Serial.println("Safe Mode Triggered: Turning off all hardware.");
  digitalWrite(BASE_LED, LOW);
  for (int i = 0; i < NUM_NODES; i++) {
    digitalWrite(NODE_PINS[i], HIGH); // Assuming Active Low, HIGH is OFF
  }
}

// Configures GPIOs
void setupPins() {
  pinMode(BASE_LED, OUTPUT);
  digitalWrite(BASE_LED, LOW); // Start LED off
  
  for (int i = 0; i < NUM_NODES; i++) {
    pinMode(NODE_PINS[i], OUTPUT);
    digitalWrite(NODE_PINS[i], HIGH); // Initialize as OFF (Active Low)
  }
  Serial.println("Hardware: 3-Node GPIO Initialized.");
}

// Generates the status string for Discovery packets
// Format: ON,OFF,ON
String getStatusString() {
  String status = "";
  for (int i = 0; i < NUM_NODES; i++) {
    // If logic is inverted for your relays, swap LOW/HIGH
    status += (digitalRead(NODE_PINS[i]) == LOW ? "ON" : "OFF");
    if (i < NUM_NODES - 1) status += ",";
  }
  return status;
}

// Main logic for processing commands
void executeCommand(String cmd) {
  Serial.println("Hardware executing: " + cmd);

  // Global Commands
  if (cmd == "BASE_ON") {
    digitalWrite(BASE_LED, HIGH);
    for (int i = 0; i < NUM_NODES; i++) digitalWrite(NODE_PINS[i], LOW);
  } 
  else if (cmd == "BASE_OFF") {
    triggerTotalShutdown();
  }
  
  // Node Specific Commands (e.g., NODE_1_ON, NODE_1_OFF)
  else if (cmd.startsWith("NODE_")) {
    int nodeNum = cmd.substring(5, 6).toInt(); // Gets "1" from "NODE_1"
    if (nodeNum >= 1 && nodeNum <= NUM_NODES) {
      if (cmd.endsWith("_ON")) {
        digitalWrite(NODE_PINS[nodeNum - 1], LOW); // Turn ON
      } else if (cmd.endsWith("_OFF")) {
        digitalWrite(NODE_PINS[nodeNum - 1], HIGH); // Turn OFF
      }
    }
  }
}
