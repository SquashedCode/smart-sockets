// base_commands.ino

// GPIO Mapping for Breadboard (Avoids restricted pins 0, 3, 1, 34, 35, 36, 39)
const int BASE_LED = 2;   // Status LED
const int NODE_PINS[8] = {4, 5, 18, 19, 21, 22, 23, 13};  // Pins subject to change by hardware managers

void setupPins() {
  pinMode(BASE_LED, OUTPUT);
  digitalWrite(BASE_LED, LOW);

  for (int i = 0; i < 8; i++) {
    pinMode(NODE_PINS[i], OUTPUT);
    digitalWrite(NODE_PINS[i], LOW); // Ensure Base starts powered off
  }
  Serial.println("8-Node GPIO Initialized.");
}

void triggerTotalShutdown() { // Safe Mode Actuation
  // Hard-kill all 8 nodes plus flashing Safe Mode LED
  digitalWrite(BASE_LED, LOW);
  for (int i = 0; i < 8; i++) {
    digitalWrite(NODE_PINS[i], LOW);
  }
  Serial.println("Connection lost, activating Safe Mode.");
  
  // Lock system to prevent phantom restarts
  while(true) { delay(1000); }
}

void executeCommand(String cmd) {
  Serial.println("Processing: " + cmd);

  // Check for Entire Base Kill Switch
  if (cmd.indexOf("BASE " + LOCK_CODE + " OFF") >= 0) {
    triggerTotalShutdown();
    return;
  }

  // Check for Individual Node Commands (1-8)
  for (int i = 1; i <= 8; i++) {
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

  // Check for Global Base ON
  if (cmd.indexOf("BASE " + LOCK_CODE + " ON") >= 0) {
    digitalWrite(BASE_LED, HIGH);
    for (int i = 0; i < 8; i++) {
      digitalWrite(NODE_PINS[i], HIGH);
    }
  }
}