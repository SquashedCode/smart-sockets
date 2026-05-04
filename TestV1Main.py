import socket
import json
import time
import threading
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, db


# =========================
# USER CONFIG
# =========================

FIREBASE_DB_URL = "https://team-socket-default-rtdb.firebaseio.com/"
SERVICE_ACCOUNT_PATH = "serviceAccountKey.json"

USER_ID = "User1"
HUB_NAME = "Hub1"

UDP_PORT = 50000
DISCOVERY_TIMEOUT = 5
COMMAND_CHECK_INTERVAL = 5

BROADCAST_IP = "255.255.255.255"


# =========================
# FIREBASE SETUP
# =========================

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred, {
            "databaseURL": FIREBASE_DB_URL
        })


def device_base_ref(base_name):
    return db.reference(f"DeviceList/{USER_ID}/{HUB_NAME}/{base_name}")


def command_list_ref():
    return db.reference("CommandList/Commands")


# =========================
# UDP HELPERS
# =========================

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()

    return ip


def send_udp_packet(ip, port, packet):
    data = json.dumps(packet).encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.sendto(data, (ip, port))
        return True
    except Exception as e:
        print(f"[UDP ERROR] Could not send packet to {ip}:{port}")
        print(e)
        return False
    finally:
        sock.close()


# =========================
# DISCOVERY
# =========================

def build_discovery_packet():
    return {
        "Type": "Discovery",
        "Hub": HUB_NAME,
        "HubIP": get_local_ip(),
        "Time": datetime.now().isoformat()
    }


def parse_discovery_response(data, addr):
    try:
        packet = json.loads(data.decode("utf-8"))
    except Exception:
        return None

    packet_type = packet.get("Type", "")

    if packet_type not in ["DiscoveryResponse", "Discovery_Response"]:
        return None

    base_name = packet.get("Base") or packet.get("name") or packet.get("DeviceName")

    if not base_name:
        base_name = f"Base_{addr[0].replace('.', '_')}"

    return {
        "name": str(base_name),
        "ip": str(addr[0]),
        "Status_base": "Online",
        "Node_L": {
            "Attached": bool(packet.get("Node_L_Attached", False)),
            "Power": bool(packet.get("Node_L_Power", False))
        },
        "Node_R": {
            "Attached": bool(packet.get("Node_R_Attached", False)),
            "Power": bool(packet.get("Node_R_Power", False))
        }
    }


def add_or_update_base_in_firebase(base_info):
    base_name = base_info["name"]
    ref = device_base_ref(base_name)

    existing = ref.get()

    if existing is None:
        ref.set(base_info)
        print(f"[FIREBASE] Added new base: {base_name}")
    else:
        ref.update({
            "ip": base_info["ip"],
            "Status_base": "Online",
            "Node_L": base_info["Node_L"],
            "Node_R": base_info["Node_R"]
        })
        print(f"[FIREBASE] Updated existing base: {base_name}")


def discover_devices():
    print("\n[DISCOVERY] Sending discovery broadcast...")

    discovery_packet = build_discovery_packet()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(DISCOVERY_TIMEOUT)

    discovered = []

    try:
        sock.sendto(json.dumps(discovery_packet).encode("utf-8"), (BROADCAST_IP, UDP_PORT))
        print(f"[DISCOVERY] Broadcast sent on port {UDP_PORT}")
        print(f"[DISCOVERY] Listening for responses for {DISCOVERY_TIMEOUT} seconds...\n")

        start_time = time.time()

        while time.time() - start_time < DISCOVERY_TIMEOUT:
            try:
                data, addr = sock.recvfrom(2048)
                base_info = parse_discovery_response(data, addr)

                if base_info:
                    print(f"[DISCOVERY] Response from {addr[0]}: {base_info['name']}")
                    add_or_update_base_in_firebase(base_info)
                    discovered.append(base_info)

            except socket.timeout:
                break

    finally:
        sock.close()

    print(f"\n[DISCOVERY] Finished. Found {len(discovered)} device(s).\n")
    return discovered


# =========================
# COMMAND PROCESSING
# =========================

def build_power_packet(command):
    return {
        "Type": "PowerCommand",
        "Hub": command.get("Hub", HUB_NAME),
        "Base": command.get("Base", ""),
        "Node": command.get("Node", ""),
        "Action": command.get("Action", "Power"),
        "Value": command.get("Value", ""),
        "Time": datetime.now().isoformat()
    }


def update_command_status(command_id, status):
    command_list_ref().child(command_id).update({
        "Status": status,
        "Time": datetime.now().isoformat()
    })


def process_power_command(command_id, command):
    base_name = command.get("Base")
    node = command.get("Node")
    value = command.get("Value")

    if not base_name or not node or value is None:
        print(f"[COMMAND] Invalid power command: {command_id}")
        update_command_status(command_id, "Failed")
        return

    base_data = device_base_ref(base_name).get()

    if not base_data:
        print(f"[COMMAND] Base not found in Firebase: {base_name}")
        update_command_status(command_id, "Failed")
        return

    base_ip = base_data.get("ip")

    if not base_ip:
        print(f"[COMMAND] No IP found for base: {base_name}")
        update_command_status(command_id, "Failed")
        return

    packet = build_power_packet(command)

    print(f"[COMMAND] Sending power command to {base_name} at {base_ip}")
    success = send_udp_packet(base_ip, UDP_PORT, packet)

    if success:
        bool_power = str(value).lower() in ["true", "high", "on", "1"]

        if node in ["Node_L", "Node_R"]:
            device_base_ref(base_name).child(node).update({
                "Power": bool_power
            })

        update_command_status(command_id, "Complete")
        print(f"[COMMAND] Command complete: {command_id}")
    else:
        update_command_status(command_id, "Failed")


def process_command(command_id, command):
    action = command.get("Action", "").lower()
    target_hub = command.get("Hub", "")

    if target_hub != HUB_NAME:
        return

    update_command_status(command_id, "Processing")

    if action == "power":
        process_power_command(command_id, command)
    else:
        print(f"[COMMAND] Unknown action: {action}")
        update_command_status(command_id, "Failed")


def command_polling_loop(stop_event):
    print("[BACKGROUND] Firebase command polling started.")

    while not stop_event.is_set():
        try:
            commands = command_list_ref().get()

            if commands:
                for command_id, command in commands.items():
                    if not isinstance(command, dict):
                        continue

                    if command.get("Status") == "Pending":
                        print(f"[BACKGROUND] Pending command found: {command_id}")
                        process_command(command_id, command)

        except Exception as e:
            print("[BACKGROUND ERROR] Firebase command polling failed.")
            print(e)

        time.sleep(COMMAND_CHECK_INTERVAL)


# =========================
# MENU FUNCTIONS
# =========================

def list_devices():
    devices = db.reference(f"DeviceList/{USER_ID}/{HUB_NAME}").get()

    print("\n========== CONNECTED DEVICES ==========")

    if not devices:
        print("No devices found.")
        print("=======================================\n")
        return

    for base_name, data in devices.items():
        print(f"\nBase: {base_name}")
        print(f"IP: {data.get('ip', 'Unknown')}")
        print(f"Status: {data.get('Status_base', 'Unknown')}")

        node_l = data.get("Node_L", {})
        node_r = data.get("Node_R", {})

        print(f"Node_L Attached: {node_l.get('Attached', False)}")
        print(f"Node_L Power: {node_l.get('Power', False)}")
        print(f"Node_R Attached: {node_r.get('Attached', False)}")
        print(f"Node_R Power: {node_r.get('Power', False)}")

    print("\n=======================================\n")


def menu_loop():
    while True:
        print("========== HUB MENU ==========")
        print("1. Discover Devices")
        print("2. List Devices")
        print("3. Exit")
        print("==============================")

        choice = input("Select option: ").strip()

        if choice == "1":
            discover_devices()
        elif choice == "2":
            list_devices()
        elif choice == "3":
            print("Exiting hub program.")
            break
        else:
            print("Invalid option.\n")


# =========================
# MAIN
# =========================

def main():
    init_firebase()

    stop_event = threading.Event()

    command_thread = threading.Thread(
        target=command_polling_loop,
        args=(stop_event,),
        daemon=True
    )

    command_thread.start()

    try:
        menu_loop()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received.")
    finally:
        stop_event.set()
        print("Hub shutting down.")


if __name__ == "__main__":
    main()
