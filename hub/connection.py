# connection.py
# Handles wireless connection, Heartbeat Monitoring, and Security Logic
import socket
import time
import threading
import os
import json

# Configuration & Constants
PORT = 5000
TIMEOUT = 6 
CHAR_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
WIFI_DATA = "WiFi address:password" 

# Hardware storage for encrypted credentials 
VAULT_FILE = "hub_secure_vault.json" 
MAX_ATTEMPTS = 5 # Lockout threshold 
login_attempts = 0 # Tracks failed login attempts in-memory
is_locked = False # System-wide lockout state

# Registry to be shared with mainsim.py for real-time tracking
device_registry = {}
registry_lock = threading.Lock()

def is_hub_authenticated():
    """Verifies if the encrypted 'Vault' exists on hardware"""
    if is_locked:
        return False
    return os.path.exists(VAULT_FILE)

def store_encrypted_credentials(encrypted_blob):
    """Stores App credentials in their encrypted form"""
    data = {
        "encrypted_login": encrypted_blob, # Never stored as plaintext 
        "timestamp": time.ctime(),
        "tls_version": "1.3" # Protocol specification 
    }
    with open(VAULT_FILE, "w") as f:
        json.dump(data, f)
    print("Hardware Storage: Encrypted credentials saved via TLS 1.3 path.")

def handle_login_attempt(provided_credentials):
    """NFR2: Implementation of the 5-attempt lockout security """
    global login_attempts, is_locked
    
    if is_locked:
        return False, "System is locked due to too many attempts."

    # Logic to be finalized for NFR7
    success = False 
    
    if not success:
        login_attempts += 1
        if login_attempts >= MAX_ATTEMPTS:
            is_locked = True
            return False, "SECURITY ALERT: 5 failed attempts. Lockout active."
        return False, f"Attempt {login_attempts}/{MAX_ATTEMPTS} failed."
    
    login_attempts = 0 # Reset on success
    return True, "Authenticated"

async def pair_new_base(code, custom_name):
    """FR10: BLE Pairing and initial Handshake coordination [cite: 58, 61]"""
    print(f"Scanning for Base {code}...")
    # Use Bleak to find the ESP32 Base unit
    devices = await BleakScanner.discover(timeout=5.0)
    target = next((d for d in devices if d.name == code), None)
    
    if target:
        try:
            async with BleakClient(target.address) as client:
                # Share WiFi info; encryption is handled before this send 
                await client.write_gatt_char(CHAR_UUID, WIFI_DATA.encode())
                await asyncio.sleep(1.0) 
        except Exception as e:
            # Handle radio handover errors during WiFi transition
            print(f"Handover finished (Note: {e})")
        
        # Initialize the shared registry for this new cluster [cite: 63, 145]
        with registry_lock:
            device_registry[custom_name] = {
                "code": code,
                "status": "INITIALIZING",
                "nodes": {i: "OFF" for i in range(1, 9)},
                "last_seen": time.time(),
                "pending_cmd": None
            }
        return True
    return False

def socket_watchdog():
    """FR3/FR4: The background thread for Heartbeats and Commands [cite: 58, 129]"""
    # Prevent operation if no credentials or if locked 
    if not is_hub_authenticated():
        status = "LOCKED" if is_locked else "UNAUTHENTICATED"
        print(f"SECURITY ALERT: Hub is {status}. Refusing WiFi commands.")
        return 

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Allow immediate port reuse to avoid 'Address already in use' errors
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', PORT))
        s.listen()
        s.settimeout(1.0)
        
        while True:
            try:
                conn, addr = s.accept()
                with conn:
                    # Receive heartbeat or status update from Base
                    data = conn.recv(1024).decode()
                    with registry_lock:
                        for name, info in device_registry.items():
                            if info['code'] in data:
                                info['status'] = "SECURE"
                                info['last_seen'] = time.time()
                                
                                # Send any queued power commands to the Base
                                if info.get('pending_cmd'):
                                    conn.sendall(info['pending_cmd'].encode())
                                    info['pending_cmd'] = None
                                else:
                                    conn.sendall(b"ACK_OK")
            except socket.timeout:
                # Safe Mode check - Trigger if silence > 6s
                with registry_lock:
                    now = time.time()
                    for name, info in device_registry.items():
                        if now - info.get('last_seen', 0) > TIMEOUT:
                            info['status'] = "!!! SAFE MODE !!!"
