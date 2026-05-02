import curses
import threading
import socket
import connection
import commands

# --- UI State ---
menu_items = ["Discover Devices", "Devices", "Hub Settings", "Network Status", "About"]
current_selection = 0
current_screen = "MAIN_MENU"

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(('8.8.8.8', 80)); ip = s.getsockname()[0]
    except: ip = "127.0.0.1"
    finally: s.close()
    return ip

def draw_menu(stdscr):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    
    
    stdscr.addstr(0, 0, "Senior Design Hub", curses.A_BOLD)
    stdscr.addstr(1, 0, "-" * w)

    if current_screen == "MAIN_MENU":
        for idx, item in enumerate(menu_items):
            if idx == current_selection:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(3 + idx, 2, f"> {item}")
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(3 + idx, 2, f"  {item}")

    else:
        # Sub-page layout
        stdscr.addstr(2, 0, "BACK to return to Menu", curses.A_DIM)
        stdscr.addstr(4, 0, "-----------------------")
        
        if current_screen == "DISCOVER":
            stdscr.addstr(5, 0, "Enter 9-digit Base Code:")
            # Logic here handles the input
        elif current_screen == "DEVICES":
            with connection.registry_lock:
                if not connection.device_registry:
                    stdscr.addstr(5, 0, "No devices discovered yet.")
                    stdscr.addstr(6, 0, "Return and choose Discover.")
                else:
                    y = 5
                    for name, info in connection.device_registry.items():
                        stdscr.addstr(y, 0, f"{name}: {info['status']}")
                        y += 1
        elif current_screen == "SETTINGS":
            stdscr.addstr(5, 0, "Hub Name: Senior Design Hub")
            stdscr.addstr(6, 0, 'Rename is handled by UDP: {"type":"RENAME_HUB","new_name":"New Name"}')
        elif current_screen == "NETWORK":
            stdscr.addstr(5, 0, f"Hub IP: {get_ip()}")
            stdscr.addstr(6, 0, f"UDP Port: 5000")
            stdscr.addstr(7, 0, f"Devices: {len(connection.device_registry)}")
            stdscr.addstr(8, 0, f"Broadcast: 255.255.255.255")
        elif current_screen == "ABOUT":
            stdscr.addstr(5, 0, "Senior Design Hub")
            stdscr.addstr(6, 0, "UDP Discovery System")
            stdscr.addstr(7, 0, "Raspberry Pi + ESP32")
            stdscr.addstr(8, 0, "LEFT returns to menu")

    stdscr.refresh()

def run_menu(stdscr):
    global current_selection, current_screen
    curses.curs_set(0) # Hide cursor
    
    while True:
        draw_menu(stdscr)
        key = stdscr.getch()

        # Navigation Logic
        if current_screen == "MAIN_MENU":
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(menu_items) - 1:
                current_selection += 1
            elif key == 10: # Enter key
                current_screen = menu_items[current_selection].upper().replace(" ", "_")
                # Mapping screens
                if current_screen == "DISCOVER_DEVICES": current_screen = "DISCOVER"
                elif current_screen == "DEVICES": current_screen = "DEVICES"
                elif current_screen == "HUB_SETTINGS": current_screen = "SETTINGS"
                elif current_screen == "NETWORK_STATUS": current_screen = "NETWORK"
                elif current_screen == "ABOUT": current_screen = "ABOUT"
        else:
            # Back logic (Any key returns to menu, or specifically LEFT/Back)
            if key == ord('q') or key == curses.KEY_LEFT:
                current_screen = "MAIN_MENU"

        # Specific Input Logic for Pairing
        if current_screen == "DISCOVER":
             # Implementation of Numpad input would go here
             # You can use stdscr.getstr() for this
             pass

def main():
    # Start background threads
    threading.Thread(target=connection.socket_watchdog, daemon=True).start()
    threading.Thread(target=connection.firebase_listener, daemon=True).start()
    
    # Start UI
    curses.wrapper(run_menu)

if __name__ == "__main__":
    main()
