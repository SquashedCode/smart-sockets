#!/usr/bin/env python3

import socket
import json
import time
import threading
import os
from datetime import datetime

import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont

# ------------------------------------------------------------
# Firebase import
# ------------------------------------------------------------

try:
    import firebase_admin
    from firebase_admin import credentials
    from firebase_admin import db
except ImportError:
    firebase_admin = None
    credentials = None
    db = None

# ------------------------------------------------------------
# Waveshare import
# ------------------------------------------------------------

try:
    from waveshare_epd import epd4in2_V2 as epd_driver
except ImportError:
    try:
        from waveshare_epd import epd4in2 as epd_driver
    except ImportError:
        epd_driver = None

# ------------------------------------------------------------
# Basic configuration
# ------------------------------------------------------------

UDP_PORT = 50000
BROADCAST_IP = "255.255.255.255"

HUB_NAME_FILE = "hub_name.txt"
DEFAULT_HUB_NAME = "Hub_1"

DATABASE_URL = "https://team-socket-default-rtdb.firebaseio.com/"
SERVICE_ACCOUNT_FILE = "serviceAccountKey.json"
KNOWN_DEVICES_FILE = "known_devices.json"
USER_NAME = "User"
HUB_INFO_KEY = "_Hub_Info"

DISCOVERY_INTERVAL = 60
DEVICE_TIMEOUT = 180

DISPLAY_WIDTH = 400
DISPLAY_HEIGHT = 300

BUTTON_UP = 5
BUTTON_DOWN = 6
BUTTON_LEFT = 13
BUTTON_RIGHT = 19
BUTTON_SELECT = 26

BUTTON_PINS = [
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_SELECT
]

# ------------------------------------------------------------
# Hub state
# ------------------------------------------------------------

hub_name = DEFAULT_HUB_NAME
devices = {}
devices_lock = threading.Lock()

menu_layer = "main"
selected_index = 0
submenu_index = 0

main_menu = [
    "Discover Devices",
    "Devices",
    "Hub Settings",
    "Network Status",
    "About"
]

needs_display_update = True
running = True

# ------------------------------------------------------------
# Firebase and known device storage
# ------------------------------------------------------------

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

    print("Connected to Firebase")
    return True


def load_known_devices_file():
    if not os.path.exists(KNOWN_DEVICES_FILE):
        return {
            "Hub_Name": hub_name,
            "devices": {}
        }

    try:
        with open(KNOWN_DEVICES_FILE, "r") as file:
            return json.load(file)
    except json.JSONDecodeError:
        print("known_devices.json is invalid. Starting with an empty list.")
        return {
            "Hub_Name": hub_name,
            "devices": {}
        }


def save_known_devices_file(known_data):
    known_data["Hub_Name"] = hub_name

    with open(KNOWN_DEVICES_FILE, "w") as file:
        json.dump(known_data, file, indent=2)


def make_firebase_safe_device_data(device_data):
    """Return only the fields that are allowed by the current Firebase rules."""
    return {
        "name": str(device_data.get("name", "Unknown")),
        "ip": str(device_data.get("ip", "0.0.0.0")),
        "Status_base": str(device_data.get("Status_base", "Online")),
        "Node_L": {
            "Attached": bool(device_data.get("Node_L", {}).get("Attached", False)),
            "Power": bool(device_data.get("Node_L", {}).get("Power", False))
        },
        "Node_R": {
            "Attached": bool(device_data.get("Node_R", {}).get("Attached", False)),
            "Power": bool(device_data.get("Node_R", {}).get("Power", False))
        }
    }


def ensure_firebase_hub_branch():
    if firebase_admin is None or not firebase_admin._apps:
        return

    hub_ref_path = f"DeviceList/{USER_NAME}/{hub_name}"
    hub_ref = db.reference(hub_ref_path)

    # Firebase Realtime Database does not keep empty branches.
    # Your current rules also say every child under Hub_1 must look like a base.
    # This creates a rules-compatible starter child so Hub_1 exists before bases are discovered.
    hub_starter_data = make_firebase_safe_device_data({
        "name": hub_name,
        "ip": get_local_ip(),
        "Status_base": "Hub_Online",
        "Node_L": {
            "Attached": False,
            "Power": False
        },
        "Node_R": {
            "Attached": False,
            "Power": False
        }
    })

    try:
        hub_ref.child(HUB_INFO_KEY).set(hub_starter_data)
        print(f"Firebase hub branch ready: {hub_ref_path}")
    except Exception as error:
        print("Could not create Firebase hub branch:", error)


def sync_device_to_firebase(device_name, device_data):
    if firebase_admin is None or not firebase_admin._apps:
        return

    ref_path = f"DeviceList/{USER_NAME}/{hub_name}/{device_name}"
    device_ref = db.reference(ref_path)

    try:
        device_ref.set(make_firebase_safe_device_data(device_data))
    except Exception as error:
        print(f"Could not sync {device_name} to Firebase:", error)


def build_device_data(device_name, device_ip, message):
    node_l = message.get("Node_L", {
        "Attached": False,
        "Power": False
    })

    node_r = message.get("Node_R", {
        "Attached": False,
        "Power": False
    })

    return {
        "name": device_name,
        "ip": device_ip,
        "Status_base": "Online",
        "last_seen": str(time.time()),
        "Node_L": node_l,
        "Node_R": node_r
    }


def update_known_device(device_name, device_ip, message):
    known_data = load_known_devices_file()
    known_devices = known_data["devices"]
    device_data = build_device_data(device_name, device_ip, message)

    if device_name in known_devices:
        old_ip = known_devices[device_name].get("ip")

        if old_ip != device_ip:
            print(f"{device_name} IP updated: {old_ip} -> {device_ip}")
        else:
            print(f"{device_name} already known")
    else:
        print(f"New device discovered: {device_name}")

    known_devices[device_name] = device_data
    save_known_devices_file(known_data)
    sync_device_to_firebase(device_name, device_data)

    return device_data


def load_known_devices_into_memory():
    global devices
    global needs_display_update

    known_data = load_known_devices_file()

    with devices_lock:
        devices = {}

        for device_name, device_data in known_data.get("devices", {}).items():
            devices[device_name] = {
                "name": device_data.get("name", device_name),
                "ip": device_data.get("ip", "Unknown"),
                "status": device_data.get("Status_base", "Unknown"),
                "last_seen": float(device_data.get("last_seen", time.time())),
                "raw": device_data
            }

    needs_display_update = True

# ------------------------------------------------------------
# Name storage
# ------------------------------------------------------------

def load_hub_name():
    global hub_name

    if os.path.exists(HUB_NAME_FILE):
        with open(HUB_NAME_FILE, "r") as file:
            name = file.read().strip()

        if name:
            hub_name = name


def save_hub_name(new_name):
    global hub_name

    hub_name = new_name

    with open(HUB_NAME_FILE, "w") as file:
        file.write(hub_name)

# ------------------------------------------------------------
# UDP network functions
# ------------------------------------------------------------

def create_udp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", UDP_PORT))
    sock.settimeout(0.5)
    return sock


udp_socket = None


def send_udp_message(message, ip=BROADCAST_IP, port=UDP_PORT):
    global udp_socket

    data = json.dumps(message).encode("utf-8")
    udp_socket.sendto(data, (ip, port))


def send_discovery():
    message = {
        "type": "DISCOVERY",
        "Action": "Discovery",
        "sender": hub_name,
        "Hub_Name": hub_name,
        "role": "hub",
        "port": UDP_PORT
    }

    send_udp_message(message)


def send_ping_to_device(ip):
    message = {
        "type": "PING",
        "Action": "Heartbeat",
        "sender": hub_name,
        "Hub_Name": hub_name,
        "role": "hub"
    }

    send_udp_message(message, ip=ip)


def is_discovery_response(message):
    msg_type = message.get("type", "")
    action = message.get("Action", "")

    return msg_type == "DISCOVERY_RESPONSE" or action == "Discovery_Response"


def handle_udp_message(data, address):
    global needs_display_update

    ip = address[0]

    try:
        message = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print("Received non-JSON packet from", ip)
        return

    msg_type = message.get("type", "")
    action = message.get("Action", "")

    if is_discovery_response(message):
        name = message.get("device_name") or message.get("name") or "Unknown ESP"
        device_data = update_known_device(name, ip, message)

        with devices_lock:
            devices[name] = {
                "name": name,
                "ip": ip,
                "status": device_data.get("Status_base", "Online"),
                "last_seen": time.time(),
                "raw": device_data
            }

        print(f"Discovery synced: {name} at {ip}")
        needs_display_update = True

    elif msg_type in ["PONG", "STATUS"] or action == "Heartbeat":
        name = message.get("device_name") or message.get("name") or ip
        status = message.get("status") or message.get("Status_base") or "Online"

        with devices_lock:
            devices[name] = {
                "name": name,
                "ip": ip,
                "status": status,
                "last_seen": time.time(),
                "raw": message
            }

        print(f"Device updated: {name} at {ip}, status={status}")
        needs_display_update = True

    elif msg_type == "RENAME_HUB":
        new_name = message.get("new_name")

        if new_name:
            save_hub_name(new_name)
            print("Hub renamed to:", new_name)
            needs_display_update = True

    else:
        print("Unknown message from", ip, message)


def udp_listener_thread():
    global running

    while running:
        try:
            data, address = udp_socket.recvfrom(4096)
            handle_udp_message(data, address)
        except socket.timeout:
            pass
        except Exception as error:
            print("UDP listener error:", error)


def discovery_thread():
    global running

    while running:
        send_discovery()
        time.sleep(DISCOVERY_INTERVAL)


def heartbeat_thread():
    global running
    global needs_display_update

    while running:
        now = time.time()

        with devices_lock:
            for device_name in list(devices.keys()):
                age = now - devices[device_name]["last_seen"]

                if age > DEVICE_TIMEOUT:
                    print("Marking stale device offline:", devices[device_name]["name"])
                    devices[device_name]["status"] = "Offline"
                    devices[device_name]["raw"]["Status_base"] = "Offline"
                    sync_device_to_firebase(device_name, devices[device_name]["raw"])
                    needs_display_update = True
                else:
                    send_ping_to_device(devices[device_name]["ip"])

        time.sleep(DISCOVERY_INTERVAL)

# ------------------------------------------------------------
# Button setup and reading
# ------------------------------------------------------------

def setup_buttons():
    GPIO.setmode(GPIO.BCM)

    for pin in BUTTON_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def button_pressed(pin):
    return GPIO.input(pin) == GPIO.LOW


def wait_for_button_release(pin):
    while button_pressed(pin):
        time.sleep(0.02)


def check_buttons():
    global selected_index
    global submenu_index
    global menu_layer
    global needs_display_update

    if button_pressed(BUTTON_UP):
        if menu_layer == "main":
            selected_index = (selected_index - 1) % len(main_menu)

        wait_for_button_release(BUTTON_UP)
        needs_display_update = True

    elif button_pressed(BUTTON_DOWN):
        if menu_layer == "main":
            selected_index = (selected_index + 1) % len(main_menu)

        wait_for_button_release(BUTTON_DOWN)
        needs_display_update = True

    elif button_pressed(BUTTON_LEFT):
        if menu_layer != "main":
            submenu_index = max(0, submenu_index - 1)

        wait_for_button_release(BUTTON_LEFT)
        needs_display_update = True

    elif button_pressed(BUTTON_RIGHT):
        if menu_layer != "main":
            submenu_index += 1

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

            elif selected_option == "Hub Settings":
                menu_layer = "settings"
                submenu_index = 0

            elif selected_option == "Network Status":
                menu_layer = "network"
                submenu_index = 0

            elif selected_option == "About":
                menu_layer = "about"
                submenu_index = 0

        else:
            menu_layer = "main"

        wait_for_button_release(BUTTON_SELECT)
        needs_display_update = True

# ------------------------------------------------------------
# Display functions
# ------------------------------------------------------------

def get_font(size):
    possible_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "fonts/Font.ttc"
    ]

    for path in possible_fonts:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def draw_header(draw, title, font):
    draw.rectangle((0, 0, DISPLAY_WIDTH, 35), fill=0)
    draw.text((10, 8), title, font=font, fill=255)


def draw_main_menu(draw):
    title_font = get_font(18)
    item_font = get_font(22)

    draw_header(draw, hub_name, title_font)

    y = 55

    for i, item in enumerate(main_menu):
        prefix = "> " if i == selected_index else "  "
        draw.text((25, y), prefix + item, font=item_font, fill=0)
        y += 42


def draw_devices_menu(draw):
    title_font = get_font(18)
    item_font = get_font(20)
    small_font = get_font(15)

    draw_header(draw, "Devices - Select to return", title_font)

    with devices_lock:
        device_list = list(devices.values())

    if not device_list:
        draw.text((25, 70), "No devices discovered yet.", font=item_font, fill=0)
        draw.text((25, 105), "Return and choose Discover.", font=small_font, fill=0)
        return

    index = submenu_index % len(device_list)
    device = device_list[index]
    raw = device.get("raw", {})
    node_l = raw.get("Node_L", {})
    node_r = raw.get("Node_R", {})

    draw.text((25, 55), f"Device {index + 1} of {len(device_list)}", font=small_font, fill=0)
    draw.text((25, 85), f"Name: {device['name']}", font=item_font, fill=0)
    draw.text((25, 115), f"IP: {device['ip']}", font=item_font, fill=0)
    draw.text((25, 145), f"Status: {device['status']}", font=item_font, fill=0)
    draw.text((25, 175), f"L: A={node_l.get('Attached')} P={node_l.get('Power')}", font=item_font, fill=0)
    draw.text((25, 205), f"R: A={node_r.get('Attached')} P={node_r.get('Power')}", font=item_font, fill=0)

    last_seen = int(time.time() - device["last_seen"])
    draw.text((25, 235), f"Last seen: {last_seen} sec ago", font=small_font, fill=0)
    draw.text((25, 260), "LEFT/RIGHT: switch device", font=small_font, fill=0)


def draw_settings_menu(draw):
    title_font = get_font(18)
    item_font = get_font(20)

    draw_header(draw, "Hub Settings", title_font)

    draw.text((25, 70), f"Hub Name:", font=item_font, fill=0)
    draw.text((25, 105), hub_name, font=item_font, fill=0)

    draw.text((25, 170), "Rename is handled by UDP:", font=item_font, fill=0)
    draw.text((25, 205), '{"type":"RENAME_HUB",', font=item_font, fill=0)
    draw.text((25, 235), '"new_name":"New Name"}', font=item_font, fill=0)


def draw_network_menu(draw):
    title_font = get_font(18)
    item_font = get_font(20)

    draw_header(draw, "Network Status", title_font)

    local_ip = get_local_ip()

    with devices_lock:
        count = len(devices)

    draw.text((25, 70), f"Hub IP: {local_ip}", font=item_font, fill=0)
    draw.text((25, 110), f"UDP Port: {UDP_PORT}", font=item_font, fill=0)
    draw.text((25, 150), f"Devices: {count}", font=item_font, fill=0)
    draw.text((25, 190), f"Broadcast: {BROADCAST_IP}", font=item_font, fill=0)


def draw_about_menu(draw):
    title_font = get_font(18)
    item_font = get_font(20)

    draw_header(draw, "About", title_font)

    draw.text((25, 70), "Senior Design Hub", font=item_font, fill=0)
    draw.text((25, 110), "UDP Discovery System", font=item_font, fill=0)
    draw.text((25, 150), "Raspberry Pi + ESP32", font=item_font, fill=0)
    draw.text((25, 210), "SELECT returns to menu", font=item_font, fill=0)


def get_local_ip():
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_socket.connect(("8.8.8.8", 80))
        ip = test_socket.getsockname()[0]
        test_socket.close()
        return ip
    except Exception:
        return "Unavailable"


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

# ------------------------------------------------------------
# Main program
# ------------------------------------------------------------

def main():
    global udp_socket
    global needs_display_update
    global running

    load_hub_name()
    init_firebase()
    ensure_firebase_hub_branch()
    load_known_devices_into_memory()
    setup_buttons()

    udp_socket = create_udp_socket()

    epd = setup_display()

    threading.Thread(target=udp_listener_thread, daemon=True).start()
    threading.Thread(target=discovery_thread, daemon=True).start()
    threading.Thread(target=heartbeat_thread, daemon=True).start()

    print("Hub started.")
    print("Hub name:", hub_name)
    print("Listening on UDP port:", UDP_PORT)
    print("Local IP:", get_local_ip())

    send_discovery()

    try:
        while True:
            check_buttons()

            if needs_display_update:
                update_display(epd)
                needs_display_update = False

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("Shutting down...")

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
