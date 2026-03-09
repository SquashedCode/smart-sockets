import socket
import time
import threading
from bleak import BleakScanner, BleakClient

# --- Configuration ---
PORT = 5000
TIMEOUT = 6 
CHAR_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
WIFI_DATA = "WiFi address:password" #Fill in for respective WiFi

# Registry to be shared with mainsim.py
device_registry = {}
registry_lock = threading.Lock()

async def pair_new_base(code, custom_name):
    """BLE Pairing with handover error handling"""
    print(f"Scanning for Base {code}...")
    devices = await BleakScanner.discover(timeout=5.0)
    target = next((d for d in devices if d.name == code), None)
    
    if target:
        try:
            async with BleakClient(target.address) as client:
                await client.write_gatt_char(CHAR_UUID, WIFI_DATA.encode())
                await asyncio.sleep(1.0) # Wait for radio handover
        except Exception as e:
            print(f"Handover finished (Note: {e})")
        
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
    """Heartbeat Monitoring"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        s.bind(('0.0.0.0', PORT))
        s.listen()
        s.settimeout(1.0)
        
        while True:
            try:
                conn, addr = s.accept()
                with conn:
                    data = conn.recv(1024).decode()
                    with registry_lock:
                        for name, info in device_registry.items():
                            if info['code'] in data:
                                info['status'] = "SECURE"
                                info['last_seen'] = time.time()
                                
                                # Check for commands from power_controller
                                if info.get('pending_cmd'):
                                    conn.sendall(info['pending_cmd'].encode())
                                    info['pending_cmd'] = None
                                else:
                                    conn.sendall(b"ACK_OK")
            except socket.timeout:
                # Watchdog timeout check
                with registry_lock:
                    now = time.time()
                    for name, info in device_registry.items():
                        if now - info.get('last_seen', 0) > TIMEOUT:
                            info['status'] = "!!! SAFE MODE !!!"
