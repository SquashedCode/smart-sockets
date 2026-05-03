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
  int pinIdx = -1;
  
  // Mapping JSON nodes to hardware indices
  if (node == "Node_L") pinIdx = 0;
  else if (node == "Node_R") pinIdx = 1;
  else if (node == "NONE") { /* Apply to all? */ }

  if (pinIdx != -1) {
    if (value == "High") digitalWrite(NODE_PINS[pinIdx], LOW); // Assuming Active Low
    else digitalWrite(NODE_PINS[pinIdx], HIGH);
  }
}
