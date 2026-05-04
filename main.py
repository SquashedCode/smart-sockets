#!/usr/bin/env python3

import socket
import json
import time
import threading
import os

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

HUB_NAME_FILE = "hub_name.txt"
DEFAULT_HUB_NAME = "hub_1"

DATABASE_URL = "https://team-socket-default-rtdb.firebaseio.com/"
SERVICE_ACCOUNT_FILE = "serviceAccountKey.json"

USER_NAME = "user"
HUB_INFO_KEY = "_hub_info"

DISCOVERY_INTERVAL = 5
DEVICE_TIMEOUT = 20

DISPLAY_WIDTH = 400
DISPLAY_HEIGHT = 300

FONT_HEADER = 26
FONT_MAIN_ITEM = 30
FONT_ITEM = 26
FONT_SMALL = 18
HEADER_HEIGHT = 48

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


#------------------------------------------------------------
# HUB STATE
#------------------------------------------------------------

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
# DEBUG: PRINT UDP PACKET
#------------------------------------------------------------

def debug_print_packet(data, address):
    ip = address[0]

    try:
        message = json.loads(data.decode("utf-8"))
    except Exception:
        return

    action = clean_lower_string(message.get("action", ""))

    if action != "discovery_response":
        return

    print("\n================ UDP PACKET ================")
    print(f"FROM: {ip}")

    try:
        raw_str = data.decode("utf-8")
        print("\nRAW STRING:")
        print(raw_str)
    except Exception:
        print("\nRAW BYTES (non-utf8):")
        print(data)

    print("\nPARSED JSON:")
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
    node_l = device_data.get("node_L", {})
    node_r = device_data.get("node_R", {})

    return {
        "name": clean_lower_string(device_data.get("name", "unknown")),
        "ip": clean_string(device_data.get("ip", "0.0.0.0")),
        "Status_base": clean_lower_string(device_data.get("status_base", "online")),
        "Node_L": {
            "Attached": string_true(node_l.get("attached", "false")),
            "Power": string_true(node_l.get("power", "false"))
        },
        "Node_R": {
            "Attached": string_true(node_r.get("attached", "false")),
            "Power": string_true(node_r.get("power", "false"))
        }
    }


def firebase_to_runtime_device(device_name, device_data):
    node_l = device_data.get("Node_L", {})
    node_r = device_data.get("Node_R", {})

    return {
        "name": clean_lower_string(device_data.get("name", device_name)),
        "ip": clean_string(device_data.get("ip", "unknown")),
        "status": clean_lower_string(device_data.get("Status_base", "unknown")),
        "last_seen": time.time(),
        "raw": {
            "name": clean_lower_string(device_data.get("name", device_name)),
            "ip": clean_string(device_data.get("ip", "unknown")),
            "status_base": clean_lower_string(device_data.get("Status_base", "unknown")),
            "node_L": {
                "attached": bool_to_string(node_l.get("Attached", False)),
                "power": bool_to_string(node_l.get("Power", False))
            },
            "node_R": {
                "attached": bool_to_string(node_r.get("Attached", False)),
                "power": bool_to_string(node_r.get("Power", False))
            }
        }
    }


#------------------------------------------------------------
# FIREBASE DEVICE STORAGE
#------------------------------------------------------------

def ensure_firebase_hub_branch():
    if firebase_admin is None or not firebase_admin._apps:
        return

    hub_ref_path = f"DeviceList/{USER_NAME}/{hub_name}"
    hub_ref = db.reference(hub_ref_path)

    hub_starter_data = make_firebase_safe_device_data({
        "name": hub_name,
        "ip": get_local_ip(),
        "status_base": "hub_online",
        "node_L": {
            "attached": "false",
            "power": "false"
        },
        "node_R": {
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

    ref_path = f"DeviceList/{USER_NAME}/{hub_name}/{device_name}"
    device_ref = db.reference(ref_path)

    try:
        device_ref.set(make_firebase_safe_device_data(device_data))
    except Exception as error:
        print(f"could not sync {device_name} to firebase:", error)


def build_device_data(device_name, device_ip, message):
    node_l = message.get("node_L", {})
    node_r = message.get("node_R", {})

    return {
        "name": clean_lower_string(device_name, "unknown_esp"),
        "ip": clean_string(device_ip, "0.0.0.0"),
        "status_base": "online",
        "node_L": {
            "attached": bool_to_string(node_l.get("attached", "false")),
            "power": bool_to_string(node_l.get("power", "false"))
        },
        "node_R": {
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

    ref_path = f"DeviceList/{USER_NAME}/{hub_name}"
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

    data = json.dumps(message).encode("utf-8")
    udp_socket.sendto(data, (ip, port))


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
        "hub_IP": get_local_ip(),
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
        message = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return

    action = clean_lower_string(message.get("action", ""))

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

    elif message.get("type", "") == "rename_hub":
        new_name = message.get("new_name")

        if new_name:
            save_hub_name(new_name)
            print("hub renamed to:", hub_name)
            needs_display_update = True

    else:
        return


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
        check_for_offline_devices()
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
    item_font = get_font(FONT_ITEM)
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
    node_l = raw.get("node_L", {})
    node_r = raw.get("node_R", {})

    draw.text((25, 60), f"Device {index + 1}/{len(device_list)}", font=small_font, fill=0)
    draw.text((25, 88), f"Name: {device['name']}", font=item_font, fill=0)
    draw.text((25, 122), f"IP: {device['ip']}", font=item_font, fill=0)
    draw.text((25, 156), f"Status: {device['status']}", font=item_font, fill=0)

    draw.text(
        (25, 190),
        f"L: A={node_l.get('attached')} P={node_l.get('power')}",
        font=item_font,
        fill=0
    )

    draw.text(
        (25, 224),
        f"R: A={node_r.get('attached')} P={node_r.get('power')}",
        font=item_font,
        fill=0
    )

    last_seen = int(time.time() - device["last_seen"])
    draw.text((25, 258), f"Seen: {last_seen}s   L/R: switch", font=small_font, fill=0)


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
    title_font = get_font(FONT_HEADER)
    item_font = get_font(FONT_ITEM)
    small_font = get_font(FONT_SMALL)

    draw_header(draw, "About", title_font)

    draw.text((25, 70), "Senior Design Hub", font=item_font, fill=0)
    draw.text((25, 115), "UDP Discovery", font=item_font, fill=0)
    draw.text((25, 160), "Pi + ESP32", font=item_font, fill=0)
    draw.text((25, 230), "SELECT: back", font=small_font, fill=0)


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

    load_hub_name()
    init_firebase()
    ensure_firebase_hub_branch()
    load_devices_from_firebase()
    setup_buttons()

    udp_socket = create_udp_socket()
    epd = setup_display()

    threading.Thread(target=udp_listener_thread, daemon=True).start()
    threading.Thread(target=discovery_thread, daemon=True).start()

    print("hub started")
    print("hub name:", hub_name)
    print("listening on udp port:", UDP_PORT)
    print("local IP:", get_local_ip())

    send_discovery()

    try:
        while True:
            check_buttons()

            if needs_display_update:
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
