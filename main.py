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
DEFAULT_HUB_NAME = "Pi Central Hub"

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
        "sender": hub_name,
        "role": "hub",
        "port": UDP_PORT
    }

    send_udp_message(message)


def send_ping_to_device(ip):
    message = {
        "type": "PING",
        "sender": hub_name,
        "role": "hub"
    }

    send_udp_message(message, ip=ip)


def handle_udp_message(data, address):
    global needs_display_update

    ip = address[0]

    try:
        message = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print("Received non-JSON packet from", ip)
        return

    msg_type = message.get("type", "")

    if msg_type in ["DISCOVERY_RESPONSE", "PONG", "STATUS"]:
        name = message.get("name", "Unknown ESP")
        status = message.get("status", "unknown")

        with devices_lock:
            devices[ip] = {
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
            for ip in list(devices.keys()):
                age = now - devices[ip]["last_seen"]

                if age > DEVICE_TIMEOUT:
                    print("Removing stale device:", devices[ip]["name"])
                    del devices[ip]
                    needs_display_update = True
                else:
                    send_ping_to_device(ip)

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

    draw.text((25, 60), f"Device {index + 1} of {len(device_list)}", font=small_font, fill=0)
    draw.text((25, 95), f"Name: {device['name']}", font=item_font, fill=0)
    draw.text((25, 130), f"IP: {device['ip']}", font=item_font, fill=0)
    draw.text((25, 165), f"Status: {device['status']}", font=item_font, fill=0)

    last_seen = int(time.time() - device["last_seen"])
    draw.text((25, 200), f"Last seen: {last_seen} sec ago", font=item_font, fill=0)

    draw.text((25, 250), "LEFT/RIGHT: switch device", font=small_font, fill=0)


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
