const int NODE_PINS[3] = {2, 6, 7}; // Index 0: Node_L, Index 1: Node_R, Index 2: NONE (Center)

void setupPins() {
  for (int i = 0; i < 3; i++) {
    pinMode(NODE_PINS[i], OUTPUT);
    digitalWrite(NODE_PINS[i], HIGH); // Default OFF
  }
}

void triggerTotalShutdown() {
  for (int i = 0; i < 3; i++) digitalWrite(NODE_PINS[i], HIGH);
}

void executeCommand(String node, String value) {
  int signal = (value == "High") ? LOW : HIGH; // Active Low logic

  if (node == "ALL") {
    for (int i = 0; i < 3; i++) digitalWrite(NODE_PINS[i], signal);
  } 
  else {
    int pinIdx = -1;
    // Updated Mapping
    if (node == "Node_L") pinIdx = 0;
    else if (node == "Node_R") pinIdx = 1;
    else if (node == "NONE") pinIdx = 2; // Maps center node to pin index 2

    if (pinIdx != -1) {
      digitalWrite(NODE_PINS[pinIdx], signal);
    } else {
      Serial.println("Error: Unknown Node identifier: " + node);
    }
  }
}
