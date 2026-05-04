import socket
import json
import time

# Configuration
UDP_IP = "0.0.0.0"
UDP_PORT = 50000
BASE_NAME = "base_2" # Updated to match your request schema

class BaseStationEmulator:
    def __init__(self):
        # System State
        self.is_discovered = False
        self.is_shutdown = False
        self.is_updating = False
        self.last_discovery_received = time.time()
        
        # Pin/Node State
        self.nodes = {"node_l": "low", "node_r": "low", "node_c": "low"}
        self.led_status = "IDLE"
        
        # Socket setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((UDP_IP, UDP_PORT))
        self.sock.setblocking(False)
        
        print(f"--- Base Station Emulator Booting as {BASE_NAME} ---")
        self.update_led("IDLE")

    def update_led(self, status):
        self.led_status = status
        print(f"[PHYSICAL] LED Status updated to: {status}")

    def execute_command(self, target, value):
        if not self.is_discovered:
            print("[BLOCKED] Command ignored. Base not discovered yet.")
            return

        signal = "low" if value.lower() == "high" else "high"
        
        if target.lower() == "node_a":
            for node in self.nodes:
                self.nodes[node] = signal
            print(f"[PHYSICAL] All nodes set to {signal}")
        elif target.lower() in self.nodes:
            self.nodes[target.lower()] = signal
            print(f"[PHYSICAL] {target} set to {signal}")

    def trigger_total_shutdown(self):
        for node in self.nodes:
            self.nodes[node] = "low"
        print("[PHYSICAL] SYSTEM: Forcing all nodes OFF (LOW signal)")

    def send_packet(self, data, addr):
        msg = json.dumps(data)
        self.sock.sendto(msg.encode(), addr)
        print(f"\n[TX] ================================")
        print(f"Destination: {addr}")
        print(f"Payload: {msg}")
        print(f"====================================\n")

    def run(self):
        while True:
            # 1. Check for Timeout
            if self.is_discovered and not self.is_updating:
                if (time.time() - self.last_discovery_received) > 16.0:
                    print("!! TIMEOUT: No Discovery packet for 16s. Entering Safe Mode !!")
                    self.is_discovered = False
                    self.is_shutdown = True
                    self.trigger_total_shutdown()
                    self.update_led("SAFE_MODE")

            # 2. Check for UDP Packets
            try:
                data, addr = self.sock.recvfrom(1024)
                self.handle_packet(data, addr)
            except BlockingIOError:
                pass 
            
            time.sleep(0.1)

    def handle_packet(self, data, addr):
        raw_data = data.decode()
        print(f"\n--- UDP PACKET RECEIVED ---")
        
        try:
            doc = json.loads(raw_data)
            action = doc.get("action", "").lower()
            
            # Discovery Logic
            if action == "discovery":
                if not self.is_discovered:
                    self.is_discovered = True
                    self.last_discovery_received = time.time()
                    self.update_led("PAIRED")
                    
                    response = {
                        "base": BASE_NAME,
                        "action": "discovery_response",
                        "nodes": self.nodes
                    }
                    self.send_packet(response, addr)
                else:
                    self.last_discovery_received = time.time()

            # Power Logic (Updated to return your requested JSON)
            elif action == "power" and self.is_discovered and not self.is_shutdown:
                target = doc.get("node", "")
                val = doc.get("value", "low")
                cmd_id = doc.get("command_id", "0") # Get the ID from the Hub
                
                self.execute_command(target, val)
                
                # New response format as requested
                response = {
                    "action": "command_response",
                    "command_id": cmd_id,
                    "base": BASE_NAME,
                    "status": "successful",
                    "node_L": {
                        "attached": "true",
                        "power": "true" if self.nodes["node_l"] == "high" else "false"
                    },
                    "node_R": {
                        "attached": "false",
                        "power": "true" if self.nodes["node_r"] == "high" else "false"
                    }
                }
                self.send_packet(response, addr)
                
        except json.JSONDecodeError:
            print("Error: Failed to parse JSON")

if __name__ == "__main__":
    emulator = BaseStationEmulator()
    emulator.run()
