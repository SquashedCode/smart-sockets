const int NODE_PINS[3] = {2, 6, 7}; // Map your indices 0, 1, 2

void setupPins() {
  for (int i = 0; i < 3; i++) {
    pinMode(NODE_PINS[i], OUTPUT);
    digitalWrite(NODE_PINS[i], HIGH); // OFF
  }
}

void triggerTotalShutdown() {
  for (int i = 0; i < 3; i++) digitalWrite(NODE_PINS[i], HIGH);
}

void executeCommand(String node, String value) {
  // Determine the target signal (High=LOW, Low=HIGH due to Active Low relay)
  int signal = (value == "High") ? LOW : HIGH;

  // Check for Global "ALL" Command
  if (node == "ALL") {
    Serial.println("Executing command on ALL nodes.");
    for (int i = 0; i < 3; i++) {
      digitalWrite(NODE_PINS[i], signal);
    }
  } 
  // Standard Individual Node Mapping
  else {
    int pinIdx = -1;
    if (node == "Node_L") pinIdx = 0;
    else if (node == "Node_R") pinIdx = 1;
    else if (node == "Node_M") pinIdx = 2;

    if (pinIdx != -1) {
      digitalWrite(NODE_PINS[pinIdx], signal);
    } else {
      Serial.println("Error: Unknown Node identifier.");
    }
  }
}
