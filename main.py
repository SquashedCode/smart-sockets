#!/usr/bin/env python3

import socket
import json
import time
import threading
import os
import hashlib
from Crypto.Cipher import AES

import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont


#------------------------------------------------------------
# FIREBASE IMPORT
#------------------------------------------------------------

try:
    import firebase_admin
    from firebase_admin import credentials
    from firebase_admin import db
except ImportError:
    firebase_admin = None
    credentials = None
    db = None


#------------------------------------------------------------
# WAVESHARE IMPORT
#------------------------------------------------------------

try:
    from waveshare_epd import epd4in2_V2 as epd_driver
except ImportError:
    try:
        from waveshare_epd import epd4in2 as epd_driver
    except ImportError:
        epd_driver = None


#------------------------------------------------------------
# BASIC CONFIGURATION
#------------------------------------------------------------

UDP_PORT = 50000
BROADCAST_IP = "255.255.255.255"
PASSKEY = "teamsocket"

HUB_NAME_FILE = "hub_name.txt"
DEFAULT_HUB_NAME = "hub_1"

DATABASE_URL = "https://team-socket-default-rtdb.firebaseio.com/"
SERVICE_ACCOUNT_FILE = "serviceAccountKey.json"

USER_NAME = "user"
HUB_INFO_KEY = "_hub_info"

# Use "commands" instead if your Firebase tree is lowercase.
COMMANDS_PATH = "command_list/commands"
COMMAND_POLL_INTERVAL = 1.0

DISCOVERY_INTERVAL = 5
DEVICE_TIMEOUT = 20

SCREENSAVER_TIMEOUT = 30
screensaver_active = False
last_activity_time = time.time()

DISPLAY_WIDTH = 400
DISPLAY_HEIGHT = 300

FONT_HEADER = 26
FONT_MAIN_ITEM = 30
FONT_ITEM = 26
FONT_SMALL = 18
HEADER_HEIGHT = 48

BUTTON_UP = 6
BUTTON_DOWN = 19
BUTTON_LEFT = 5
BUTTON_RIGHT = 13
BUTTON_SELECT = 26

BUTTON_PINS = [
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_SELECT
]


#------------------------------------------------------------
# HUB STATE
#------------------------------------------------------------

hub_name = DEFAULT_HUB_NAME
devices = {}
devices_lock = threading.Lock()

menu_layer = "main"
selected_index = 0
submenu_index = 0
device_control_index = 0

main_menu = [
    "Discover Devices",
    "Devices",
    "Hub Settings",
    "Network Status",
    "About"
]

needs_display_update = True
running = True
udp_socket = None


#------------------------------------------------------------
# STRING HELPERS
#------------------------------------------------------------

def clean_string(value, default=""):
    if value is None:
        return default

    return str(value)


def clean_lower_string(value, default=""):
    if value is None:
        return default

    return str(value).strip().lower()


def string_true(value):
    return clean_lower_string(value) in ["true", "1", "on", "high", "yes"]


def bool_to_string(value):
    if isinstance(value, str):
        return "true" if string_true(value) else "false"

    return "true" if bool(value) else "false"


#------------------------------------------------------------
# DEBUG: PRINT  PACKET
#------------------------------------------------------------

def debug_print_packet(data, address):
    ip = address[0]

    try:
        decrypted = decrypt_packet(data)
        message = json.loads(decrypted.decode("utf-8"))
    except Exception:
        return

    action = clean_lower_string(message.get("action", ""))

    if action not in ["discovery_response", "command_response", "update_status"]:
        return

    print("\n================  PACKET ================")
    print(f"FROM: {ip}")
    print("\nDECRYPTED JSON:")
    print(json.dumps(message, indent=2))
    print("============================================\n")


#------------------------------------------------------------
# FIREBASE SETUP
#------------------------------------------------------------

def init_firebase():
    if firebase_admin is None:
        print("firebase-admin is not installed. Firebase sync disabled.")
        return False

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"{SERVICE_ACCOUNT_FILE} not found. Firebase sync disabled.")
        return False

    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
        firebase_admin.initialize_app(cred, {
            "databaseURL": DATABASE_URL
        })

    print("connected to firebase")
    return True


#------------------------------------------------------------
# FIREBASE DEVICE FORMAT
#------------------------------------------------------------

def make_firebase_safe_device_data(device_data):
    node_l = device_data.get("node_l", {})
    node_r = device_data.get("node_r", {})

    return {
        "name": clean_lower_string(device_data.get("name", "unknown")),
        "ip": clean_string(device_data.get("ip", "0.0.0.0")),
        "status_base": clean_lower_string(device_data.get("status_base", "online")),
        "base_power": string_true(device_data.get("base_power", "false")),
        "node_l": {
            "attached": string_true(node_l.get("attached", "false")),
            "power": string_true(node_l.get("power", "false"))
        },
        "node_r": {
            "attached": string_true(node_r.get("attached", "false")),
            "power": string_true(node_r.get("power", "false"))
        }
    }


def firebase_to_runtime_device(device_name, device_data):
    node_l = device_data.get("node_l", {})
    node_r = device_data.get("node_r", {})

    return {
        "name": clean_lower_string(device_data.get("name", device_name)),
        "ip": clean_string(device_data.get("ip", "unknown")),
        "status": clean_lower_string(device_data.get("status_base", "unknown")),
        "last_seen": time.time(),
        "raw": {
            "name": clean_lower_string(device_data.get("name", device_name)),
            "ip": clean_string(device_data.get("ip", "unknown")),
            "status_base": clean_lower_string(device_data.get("status_base", "unknown")),
            "base_power": bool_to_string(device_data.get("base_power", False)),
            "node_l": {
                "attached": bool_to_string(node_l.get("attached", False)),
                "power": bool_to_string(node_l.get("power", False))
            },
            "node_r": {
                "attached": bool_to_string(node_r.get("attached", False)),
                "power": bool_to_string(node_r.get("power", False))
            }
        }
    }


#------------------------------------------------------------
# FIREBASE DEVICE STORAGE
#------------------------------------------------------------

def ensure_firebase_hub_branch():
    if firebase_admin is None or not firebase_admin._apps:
        return

    hub_ref_path = f"device_list/{USER_NAME}/{hub_name}"
    hub_ref = db.reference(hub_ref_path)

    hub_starter_data = make_firebase_safe_device_data({
        "name": hub_name,
        "ip": get_local_ip(),
        "status_base": "hub_online",
        "node_l": {
            "attached": "false",
            "power": "false"
        },
        "node_r": {
            "attached": "false",
            "power": "false"
        }
    })

    try:
        hub_ref.child(HUB_INFO_KEY).set(hub_starter_data)
        print(f"firebase hub branch ready: {hub_ref_path}")
    except Exception as error:
        print("could not create firebase hub branch:", error)


def sync_device_to_firebase(device_name, device_data):
    if firebase_admin is None or not firebase_admin._apps:
        return

    ref_path = f"device_list/{USER_NAME}/{hub_name}/{device_name}"
    device_ref = db.reference(ref_path)

    try:
        device_ref.set(make_firebase_safe_device_data(device_data))
    except Exception as error:
        print(f"could not sync {device_name} to firebase:", error)


def build_device_data(device_name, device_ip, message):
    device_name = clean_lower_string(device_name, "unknown_esp")

    with devices_lock:
        existing_raw = devices.get(device_name, {}).get("raw", {})

    node_l = message.get("node_l", existing_raw.get("node_l", {}))
    node_r = message.get("node_r", existing_raw.get("node_r", {}))

    base_power = bool_to_string(
        message.get("base_power", existing_raw.get("base_power", "false"))
    )

    target_node = clean_lower_string(message.get("node", ""))
    value = clean_lower_string(message.get("value", ""))

    if value in ["high", "low", "true", "false", "on", "off"]:
        power_value = "true" if string_true(value) else "false"

        if target_node == "base":
            base_power = power_value

            if node_l:
                node_l["power"] = power_value

            if node_r:
                node_r["power"] = power_value

        elif target_node == "node_c":
            base_power = power_value

        elif target_node == "node_l":
            node_l["power"] = power_value

        elif target_node == "node_r":
            node_r["power"] = power_value

    return {
        "name": device_name,
        "ip": clean_string(device_ip, "0.0.0.0"),
        "status_base": "online",
        "base_power": base_power,
        "node_l": {
            "attached": bool_to_string(node_l.get("attached", "false")),
            "power": bool_to_string(node_l.get("power", "false"))
        },
        "node_r": {
            "attached": bool_to_string(node_r.get("attached", "false")),
            "power": bool_to_string(node_r.get("power", "false"))
        }
    }


def save_device_to_firebase(device_name, device_ip, message):
    device_data = build_device_data(device_name, device_ip, message)
    sync_device_to_firebase(device_name, device_data)

    return device_data


def load_devices_from_firebase():
    global devices
    global needs_display_update

    if firebase_admin is None or not firebase_admin._apps:
        return

    ref_path = f"device_list/{USER_NAME}/{hub_name}"
    firebase_devices = db.reference(ref_path).get()

    with devices_lock:
        devices = {}

        if firebase_devices:
            for device_name, device_data in firebase_devices.items():
                if device_name == HUB_INFO_KEY:
                    continue

                devices[device_name] = firebase_to_runtime_device(device_name, device_data)

    needs_display_update = True


#------------------------------------------------------------
# FIREBASE  HANDLING
#------------------------------------------------------------

def get_oldest_pending_command():
    if firebase_admin is None or not firebase_admin._apps:
        return None, None

    try:
        commands = db.reference(COMMANDS_PATH).get()
    except Exception as error:
        print("could not read commands:", error)
        return None, None

    if not commands:
        return None, None

    pending_commands = []

    for command_id, command_data in commands.items():
        if not isinstance(command_data, dict):
            continue

        status = clean_lower_string(command_data.get("status", ""))
        command_hub = clean_lower_string(command_data.get("hub", ""))

        if status == "pending" and command_hub == hub_name:
            pending_commands.append((command_id, command_data))

    if not pending_commands:
        return None, None

    def command_time(item):
        try:
            return float(item[1].get("time", 0))
        except Exception:
            return 0

    pending_commands.sort(key=command_time)

    return pending_commands[0]


def update_command_status(command_id, status):
    if firebase_admin is None or not firebase_admin._apps:
        return

    try:
        db.reference(f"{COMMANDS_PATH}/{command_id}/status").set(status)
    except Exception as error:
        print("could not update command status:", error)


def make_udp_command_packet(command_id, command_data):
    return {
        "action": clean_lower_string(command_data.get("action", "")),
        "command_id": command_id,
        "hub_name": clean_lower_string(command_data.get("hub", hub_name)),
        "base": clean_lower_string(command_data.get("base", "")),
        "node": clean_string(command_data.get("node", "all")),
        "value": clean_string(command_data.get("value", "")),
        "port": str(UDP_PORT)
    }


def get_base_ip_from_runtime_or_firebase(base_name):
    base_name = clean_lower_string(base_name)

    with devices_lock:
        if base_name in devices:
            ip = devices[base_name].get("ip", "")
            status = clean_lower_string(devices[base_name].get("status", ""))

            if ip and ip != "unknown" and status != "offline":
                return ip

    if firebase_admin is None or not firebase_admin._apps:
        return None

    try:
        device_data = db.reference(f"device_list/{USER_NAME}/{hub_name}/{base_name}").get()
    except Exception as error:
        print("could not check firebase device list:", error)
        return None

    if not device_data:
        return None

    ip = clean_string(device_data.get("ip", ""))
    status = clean_lower_string(device_data.get("status_base", ""))

    if ip and ip != "unknown" and status != "offline":
        return ip

    return None


def process_pending_command(command_id, command_data):
    base_name = clean_lower_string(command_data.get("base", ""))

    if not base_name:
        print("pending command missing base field:", command_id)
        update_command_status(command_id, "Error")
        return

    packet = make_udp_command_packet(command_id, command_data)

    update_command_status(command_id, "processing")

    base_ip = get_base_ip_from_runtime_or_firebase(base_name)

    if base_ip:
        print(f"sending command {command_id} directly to {base_name} at {base_ip}")
        send_udp_message(packet, ip=base_ip)
    else:
        print(f"{base_name} not found in device list, broadcasting command {command_id}")
        packet["broadcast_lookup"] = "true"
        send_udp_message(packet, ip=BROADCAST_IP)


def command_poll_thread():
    global running

    while running:
        command_id, command_data = get_oldest_pending_command()

        if command_id and command_data:
            process_pending_command(command_id, command_data)

        time.sleep(COMMAND_POLL_INTERVAL)


#------------------------------------------------------------
# HUB NAME STORAGE
#------------------------------------------------------------

def load_hub_name():
    global hub_name

    if os.path.exists(HUB_NAME_FILE):
        with open(HUB_NAME_FILE, "r") as file:
            name = file.read().strip()

        if name:
            hub_name = clean_lower_string(name)


def save_hub_name(new_name):
    global hub_name

    hub_name = clean_lower_string(new_name)

    with open(HUB_NAME_FILE, "w") as file:
        file.write(hub_name)


#------------------------------------------------------------
# CRYPTO HELPERS
#------------------------------------------------------------

def get_key():
    return hashlib.sha256(PASSKEY.encode("utf-8")).digest()[:16]


def add_padding(data):
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len]) * pad_len


def remove_padding(data):
    if not data:
        raise ValueError("empty decrypted packet")

    pad_len = data[-1]

    if pad_len < 1 or pad_len > 16:
        raise ValueError("bad padding")

    return data[:-pad_len]


def encrypt_packet(plain):
    key = get_key()
    iv = os.urandom(16)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = add_padding(plain)
    encrypted = cipher.encrypt(padded)

    return iv + encrypted


def decrypt_packet(packet):
    if len(packet) < 32:
        raise ValueError("packet too short")

    key = get_key()
    iv = packet[:16]
    encrypted = packet[16:]

    if len(encrypted) % 16 != 0:
        raise ValueError("ciphertext length not multiple of 16")

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plain = cipher.decrypt(encrypted)

    return remove_padding(padded_plain)


#------------------------------------------------------------
# UDP SOCKET FUNCTIONS
#------------------------------------------------------------

def create_udp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    sock.bind(("", UDP_PORT))
    sock.settimeout(0.5)

    return sock


def send_udp_message(message, ip=BROADCAST_IP, port=UDP_PORT):
    global udp_socket

    if udp_socket is None:
        print("udp socket is not ready")
        return

    plain = json.dumps(message).encode("utf-8")
    encrypted = encrypt_packet(plain)

    udp_socket.sendto(encrypted, (ip, port))

def get_local_ip():
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_socket.connect(("8.8.8.8", 80))
        ip = test_socket.getsockname()[0]
        test_socket.close()
        return ip
    except Exception:
        return "unavailable"


#------------------------------------------------------------
# DISCOVERY PACKET
#------------------------------------------------------------

def send_discovery():
    message = {
        "hub_name": hub_name,
        "hub_ip": get_local_ip(),
        "action": "discovery",
        "port": str(UDP_PORT)
    }

    send_udp_message(message)


def is_discovery_response(message):
    action = clean_lower_string(message.get("action", ""))

    return action == "discovery_response"


#------------------------------------------------------------
# UDP MESSAGE HANDLING
#------------------------------------------------------------

def handle_udp_message(data, address):
    global needs_display_update

    ip = address[0]

    try:
        decrypted = decrypt_packet(data)
        message = json.loads(decrypted.decode("utf-8"))
    except Exception as error:
        print("[UDP] decrypt/json failed:", error)
        return

    action = clean_lower_string(message.get("action", ""))

    print("UDP MESSAGE RECEIVED:")
    print(json.dumps(message, indent=2))
    print("ACTION:", action)

    if action == "discovery":
        return

    if is_discovery_response(message):
        name = (
            message.get("device_name")
            or message.get("base")
            or message.get("name")
            or "unknown_esp"
        )

        name = clean_lower_string(name)
        device_data = save_device_to_firebase(name, ip, message)

        with devices_lock:
            devices[name] = {
                "name": name,
                "ip": ip,
                "status": device_data.get("status_base", "online"),
                "last_seen": time.time(),
                "raw": device_data
            }

        print(f"discovery response synced: {name} at {ip}")
        needs_display_update = True

    elif action == "command_response":
        command_id = clean_string(message.get("command_id", ""))
        base_name = (
            message.get("base")
            or message.get("device_name")
            or message.get("name")
            or ""
        )

        base_name = clean_lower_string(base_name)
        response_status = clean_lower_string(message.get("status", ""))

        if base_name:
            device_data = save_device_to_firebase(base_name, ip, message)

            with devices_lock:
                devices[base_name] = {
                    "name": base_name,
                    "ip": ip,
                    "status": device_data.get("status_base", "online"),
                    "last_seen": time.time(),
                    "raw": device_data
                }

            print(f"command response synced: {base_name} at {ip}")
            needs_display_update = True

        if command_id:
            if response_status in ["success", "successful", "complete", "completed"]:
                update_command_status(command_id, "complete")
            else:
                update_command_status(command_id, "error")

    elif action == "update_status":
        print("[UDP] update_status received")
        handle_update_status(message, ip)

    elif message.get("type", "") == "rename_hub":
        new_name = message.get("new_name")

        if new_name:
            save_hub_name(new_name)
            print("hub renamed to:", hub_name)
            needs_display_update = True


def handle_update_status(packet, ip):
    global needs_display_update

    base_name = clean_lower_string(packet.get("base", ""))

    if not base_name:
        print("[UPDATE_STATUS] Missing base name")
        return

    device_data = save_device_to_firebase(base_name, ip, packet)

    with devices_lock:
        devices[base_name] = {
            "name": base_name,
            "ip": ip,
            "status": device_data.get("status_base", "online"),
            "last_seen": time.time(),
            "raw": device_data
        }

    needs_display_update = True
    print(f"[UPDATE_STATUS] Updated Firebase for {base_name}")

def udp_listener_thread():
    global running

    while running:
        try:
            data, address = udp_socket.recvfrom(4096)
            debug_print_packet(data, address)
            handle_udp_message(data, address)
        except socket.timeout:
            pass
        except Exception as error:
            print("udp listener error:", error)


#------------------------------------------------------------
# DISCOVERY HEARTBEAT THREAD
#------------------------------------------------------------

def discovery_thread():
    global running

    while running:
        send_discovery()
        #check_for_offline_devices()
        time.sleep(DISCOVERY_INTERVAL)


def check_for_offline_devices():
    global needs_display_update

    now = time.time()

    with devices_lock:
        for device_name in list(devices.keys()):
            age = now - devices[device_name]["last_seen"]

            if age > DEVICE_TIMEOUT:
                if devices[device_name]["status"] != "offline":
                    print("marking stale device offline:", devices[device_name]["name"])

                    devices[device_name]["status"] = "offline"
                    devices[device_name]["raw"]["status_base"] = "offline"

                    sync_device_to_firebase(device_name, devices[device_name]["raw"])

                    needs_display_update = True


#------------------------------------------------------------
# BUTTON SETUP AND READING
#------------------------------------------------------------

def setup_buttons():
    GPIO.setmode(GPIO.BCM)

    for pin in BUTTON_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def button_pressed(pin):
    return GPIO.input(pin) == GPIO.LOW


def wait_for_button_release(pin):
    while button_pressed(pin):
        time.sleep(0.02)

def get_device_control_options(device):
    raw = device.get("raw", {})
    node_l = raw.get("node_l", {})
    node_r = raw.get("node_r", {})

    options = ["base", "node_c"]

    if string_true(node_l.get("attached", "false")):
        options.append("node_l")

    if string_true(node_r.get("attached", "false")):
        options.append("node_r")

    return options


def get_selected_device():
    with devices_lock:
        device_list = list(devices.values())

    if not device_list:
        return None

    index = submenu_index % len(device_list)
    return device_list[index]


def get_current_power_value(device, target):
    raw = device.get("raw", {})

    if target == "node_c":
        return string_true(raw.get("base_power", "false"))

    if target == "base":
        base_power = string_true(raw.get("base_power", "false"))
        node_l_power = string_true(raw.get("node_l", {}).get("power", "false"))
        node_r_power = string_true(raw.get("node_r", {}).get("power", "false"))

        return base_power or node_l_power or node_r_power

    node_data = raw.get(target, {})
    return string_true(node_data.get("power", "false"))

def locally_toggle_device_state(device, target, new_value):
    global needs_display_update

    base_name = clean_lower_string(device.get("name", ""))
    power_value = "true" if new_value == "high" else "false"
    updated_raw = None

    with devices_lock:
        if base_name not in devices:
            return

        raw = devices[base_name].get("raw", {})

        if target == "node_c":
            raw["base_power"] = power_value

        elif target == "base":
            raw["base_power"] = power_value

            if "node_l" in raw:
                raw["node_l"]["power"] = power_value

            if "node_r" in raw:
                raw["node_r"]["power"] = power_value

        else:
            if target not in raw:
                raw[target] = {}

            raw[target]["power"] = power_value

        devices[base_name]["raw"] = raw
        updated_raw = raw

    needs_display_update = True

    if updated_raw:
        sync_device_to_firebase(base_name, updated_raw)

def push_menu_command_to_firebase(device, target, new_value):
    if firebase_admin is None or not firebase_admin._apps:
        return f"menu_{int(time.time())}"

    command_data = {
        "action": "power",
        "base": clean_lower_string(device.get("name", "")),
        "hub": hub_name,
        "node": target,
        "status": "processing",
        "time": str(time.time()),
        "value": new_value
    }

    try:
        command_ref = db.reference(COMMANDS_PATH).push(command_data)
        return command_ref.key
    except Exception as error:
        print("could not push menu command to firebase:", error)
        return f"menu_{int(time.time())}"


def send_menu_power_command(device, target):
    current_power = get_current_power_value(device, target)
    new_value = "low" if current_power else "high"

    command_id = push_menu_command_to_firebase(device, target, new_value)

    locally_toggle_device_state(device, target, new_value)

    packet = {
        "action": "power",
        "command_id": command_id,
        "hub_name": hub_name,
        "base": clean_lower_string(device.get("name", "")),
        "node": target,
        "value": new_value,
        "port": str(UDP_PORT),
        "source": "hub_menu"
    }

    ip = clean_string(device.get("ip", ""))

    if ip and ip not in ["unknown", "0.0.0.0", ""]:
        send_udp_message(packet, ip=ip)
    else:
        send_udp_message(packet, ip=BROADCAST_IP)

    print(f"menu command sent: {target} -> {new_value}, command_id={command_id}")

def check_buttons():
    global selected_index
    global submenu_index
    global menu_layer
    global needs_display_update
    global device_control_index
    global screensaver_active
    global last_activity_time

    any_pressed = any(button_pressed(pin) for pin in BUTTON_PINS)

    if any_pressed:
        last_activity_time = time.time()

        if screensaver_active:
            screensaver_active = False
            needs_display_update = True

            for pin in BUTTON_PINS:
                if button_pressed(pin):
                    wait_for_button_release(pin)

            return

    if button_pressed(BUTTON_UP):
        if menu_layer == "main":
            selected_index = (selected_index - 1) % len(main_menu)

        elif menu_layer == "devices":
            device = get_selected_device()

            if device:
                options = get_device_control_options(device)
                device_control_index = (device_control_index - 1) % len(options)

        wait_for_button_release(BUTTON_UP)
        needs_display_update = True

    elif button_pressed(BUTTON_DOWN):
        if menu_layer == "main":
            selected_index = (selected_index + 1) % len(main_menu)

        elif menu_layer == "devices":
            device = get_selected_device()

            if device:
                options = get_device_control_options(device)
                device_control_index = (device_control_index + 1) % len(options)

        wait_for_button_release(BUTTON_DOWN)
        needs_display_update = True

    elif button_pressed(BUTTON_LEFT):
        if menu_layer == "devices":
            menu_layer = "main"
            submenu_index = 0
            device_control_index = 0

        elif menu_layer != "main":
            menu_layer = "main"

        wait_for_button_release(BUTTON_LEFT)
        needs_display_update = True

    elif button_pressed(BUTTON_RIGHT):
        if menu_layer == "devices":
            with devices_lock:
                device_count = len(devices)

            if device_count > 0:
                submenu_index = (submenu_index + 1) % device_count
                device_control_index = 0

        wait_for_button_release(BUTTON_RIGHT)
        needs_display_update = True

    elif button_pressed(BUTTON_SELECT):
        if menu_layer == "main":
            selected_option = main_menu[selected_index]

            if selected_option == "Discover Devices":
                send_discovery()

            elif selected_option == "Devices":
                menu_layer = "devices"
                submenu_index = 0
                device_control_index = 0

            elif selected_option == "Hub Settings":
                menu_layer = "settings"
                submenu_index = 0

            elif selected_option == "Network Status":
                menu_layer = "network"
                submenu_index = 0

            elif selected_option == "About":
                menu_layer = "about"
                submenu_index = 0

        elif menu_layer == "devices":
            device = get_selected_device()

            if device:
                options = get_device_control_options(device)
                target = options[device_control_index % len(options)]
                send_menu_power_command(device, target)

        else:
            menu_layer = "main"

        wait_for_button_release(BUTTON_SELECT)
        needs_display_update = True

#------------------------------------------------------------
# FONT FUNCTIONS
#------------------------------------------------------------

def get_font(size):
    possible_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "fonts/Font.ttc"
    ]

    for path in possible_fonts:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    print("WARNING: Using tiny default PIL font")
    return ImageFont.load_default()


#------------------------------------------------------------
# DISPLAY DRAWING FUNCTIONS
#------------------------------------------------------------

def draw_header(draw, title, font):
    draw.rectangle((0, 0, DISPLAY_WIDTH, HEADER_HEIGHT), fill=0)
    draw.text((10, 10), title, font=font, fill=255)


def draw_main_menu(draw):
    title_font = get_font(FONT_HEADER)
    item_font = get_font(FONT_MAIN_ITEM)

    draw_header(draw, hub_name, title_font)

    y = 65

    for i, item in enumerate(main_menu):
        prefix = "> " if i == selected_index else "  "
        draw.text((20, y), prefix + item, font=item_font, fill=0)
        y += 48

def draw_devices_menu(draw):
    title_font = get_font(FONT_HEADER)
    item_font = get_font(20)
    small_font = get_font(FONT_SMALL)

    draw_header(draw, "Devices", title_font)

    with devices_lock:
        device_list = list(devices.values())

    if not device_list:
        draw.text((25, 75), "No devices found.", font=item_font, fill=0)
        draw.text((25, 115), "Use Discover Devices.", font=small_font, fill=0)
        draw.text((25, 250), "SELECT: back", font=small_font, fill=0)
        return

    index = submenu_index % len(device_list)
    device = device_list[index]

    raw = device.get("raw", {})
    node_l = raw.get("node_l", {})
    node_r = raw.get("node_r", {})

    options = get_device_control_options(device)
    selected_target = options[device_control_index % len(options)]

    draw.text((25, 56), f"Device {index + 1}/{len(device_list)}", font=small_font, fill=0)
    draw.text((25, 76), f"Name: {device['name']}", font=small_font, fill=0)
    draw.text((25, 96), f"Status: {device['status']}", font=small_font, fill=0)

    y = 120

    for option in options:
        prefix = "> " if option == selected_target else "  "

        if option == "base":
            label = "All"
            power = "ON" if get_current_power_value(device, "base") else "OFF"

        elif option == "node_c":
            label = "Base"
            power = "ON" if get_current_power_value(device, "node_c") else "OFF"

        elif option == "node_l":
            node_data = raw.get(option, {})
            label = "Left Node"
            power = "ON" if string_true(node_data.get("power", "false")) else "OFF"

        elif option == "node_r":
            node_data = raw.get(option, {})
            label = "Right Node"
            power = "ON" if string_true(node_data.get("power", "false")) else "OFF"
        
        draw.text(
            (25, y),
            f"{prefix}{label}: {power}",
            font=item_font,
            fill=0
        )

        y += 28

    draw.text((25, 258), "R: device  L: back  U/D: part  SEL: toggle", font=small_font, fill=0)

def draw_settings_menu(draw):
    title_font = get_font(FONT_HEADER)
    item_font = get_font(FONT_ITEM)
    small_font = get_font(FONT_SMALL)

    draw_header(draw, "Hub Settings", title_font)

    draw.text((25, 70), "Hub Name:", font=item_font, fill=0)
    draw.text((25, 105), hub_name, font=item_font, fill=0)

    draw.text((25, 165), "Rename over UDP:", font=item_font, fill=0)
    draw.text((25, 205), '{"type":"rename_hub",', font=small_font, fill=0)
    draw.text((25, 235), '"new_name":"new_name"}', font=small_font, fill=0)
    draw.text((25, 265), "SELECT: back", font=small_font, fill=0)


def draw_network_menu(draw):
    title_font = get_font(FONT_HEADER)
    item_font = get_font(FONT_ITEM)
    small_font = get_font(FONT_SMALL)

    draw_header(draw, "Network Status", title_font)

    local_ip = get_local_ip()

    with devices_lock:
        count = len(devices)

    draw.text((25, 70), "Hub IP:", font=item_font, fill=0)
    draw.text((25, 105), local_ip, font=item_font, fill=0)
    draw.text((25, 145), f"UDP Port: {UDP_PORT}", font=item_font, fill=0)
    draw.text((25, 185), f"Devices: {count}", font=item_font, fill=0)
    draw.text((25, 225), f"Broadcast: {BROADCAST_IP}", font=small_font, fill=0)
    draw.text((25, 265), "SELECT: back", font=small_font, fill=0)


def draw_about_menu(draw):
    # Fonts
    title_font = get_font(FONT_HEADER)   # header (black bar)
    large_font = get_font(34)            # largest text
    medium_font = get_font(26)           # medium text
    small_font = get_font(FONT_SMALL)    # small text
    # Header (black bar like other menus)
    draw_header(draw, "About", title_font)
    # Y positioning
    y = 65
    # Main Title
    draw.text((25, y), "Smart Socket Hub", font=large_font, fill=0)
    y += 50
    # Team Name
    draw.text((25, y), "Team Socket", font=medium_font, fill=0)
    y += 40
    # Spacing before names
    y += 10
    # Team Members (small font)
    members = [
        "Dylan Throckmorton",
        "Anurag Chemakurthi",
        "Abhijeet Chahande",
        "Harrison Gallo"
    ]
    for member in members:
        draw.text((25, y), member, font=small_font, fill=0)
        y += 28
    # Bottom instruction
    draw.text((25, 265), "SELECT: back", font=small_font, fill=0)

def render_display_image():
    image = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 255)
    draw = ImageDraw.Draw(image)

    if menu_layer == "main":
        draw_main_menu(draw)
    elif menu_layer == "devices":
        draw_devices_menu(draw)
    elif menu_layer == "settings":
        draw_settings_menu(draw)
    elif menu_layer == "network":
        draw_network_menu(draw)
    elif menu_layer == "about":
        draw_about_menu(draw)

    return image

def show_screensaver(epd):
    image_path = "img/screensaver.png"

    if not os.path.exists(image_path):
        return

    image = Image.open(image_path).convert("1")
    image = image.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT))

    if epd is None:
        return

    epd.display(epd.getbuffer(image))



#------------------------------------------------------------
# DISPLAY SETUP AND UPDATE
#------------------------------------------------------------

def setup_display():
    if epd_driver is None:
        print("Waveshare display driver not found. Running in terminal-only mode.")
        return None

    epd = epd_driver.EPD()
    epd.init()
    epd.Clear()

    return epd


def update_display(epd):
    image = render_display_image()

    if epd is None:
        os.system("clear")
        print("DISPLAY UPDATE")
        print("Layer:", menu_layer)
        print("Selected:", main_menu[selected_index])
        print("Devices:", len(devices))
        return

    epd.display(epd.getbuffer(image))


#------------------------------------------------------------
# MAIN PROGRAM
#------------------------------------------------------------

def main():
    global udp_socket
    global needs_display_update
    global running
    global screensaver_active
    global last_activity_time

    load_hub_name()
    init_firebase()
    ensure_firebase_hub_branch()
    load_devices_from_firebase()
    setup_buttons()

    udp_socket = create_udp_socket()
    epd = setup_display()

    threading.Thread(target=udp_listener_thread, daemon=True).start()
    threading.Thread(target=discovery_thread, daemon=True).start()
    threading.Thread(target=command_poll_thread, daemon=True).start()

    print("hub started")
    print("hub name:", hub_name)
    print("listening on udp port:", UDP_PORT)
    print("local IP:", get_local_ip())

    send_discovery()
    last_activity_time = time.time()

    screensaver_active = True
    needs_display_update = False
    show_screensaver(epd)

    try:
        while True:
            check_buttons()

            if not screensaver_active and time.time() - last_activity_time >= SCREENSAVER_TIMEOUT:
                screensaver_active = True
                needs_display_update = False
                show_screensaver(epd)

            if needs_display_update and not screensaver_active:
                update_display(epd)
                needs_display_update = False

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("shutting down...")

    finally:
        running = False

        if udp_socket:
            udp_socket.close()

        if epd:
            try:
                epd.sleep()
            except Exception:
                pass

        GPIO.cleanup()


if __name__ == "__main__":
    main()
