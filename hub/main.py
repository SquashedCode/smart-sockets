#!/usr/bin/env python3

"""
This is the main routine for the Smart-Socket Hub Device
It handles the flow of control, display, buttons, and networking

Display drivers are from waveshare e-Paper 
https://github.com/waveshareteam/e-Paper

All other code is written by Dylan Throckmorton
"""

import RPi.GPIO as GPIO
import time
import threading
import os
import sys

# BCM pin assignments
BTN_UP = 5
BTN_DOWN = 6
BTN_LEFT = 13
BTN_RIGHT = 19
BTN_SELECT = 26

# Menu items
MENU_ITEMS = [
    "Option 1 - Do something",
    "Option 2 - Do something else",
    "Option 3 - Another action",
    "Option 4 - Yet another action",
    "Option 5 - Exit program"
]

current_index = 0          # Which menu item is highlighted
menu_needs_redraw = True   # Flag to indicate menu redraw
lock = threading.Lock()    # Protect shared state in callbacks

def clear_screen():
    """Clear the terminal screen."""
    # ANSI clear-screen and move cursor to top-left
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def print_menu():
    """Print the menu with the current selection highlighted."""
    clear_screen()
    print("=== Button Menu ===")
    print("(Up / Down to move, Select to choose)\n")

    for i, item in enumerate(MENU_ITEMS):
        if i == current_index:
            # Highlight current item
            print(f"> {item}")
        else:
            print(f"  {item}")

    print("\nPress Ctrl+C to quit (from keyboard).")


def handle_selection(index):
    """
    Handle what happens when the user presses SELECT on a given menu item.
    For now, we just print which item was selected. You can put real actions here.
    """
    clear_screen()
    selected_item = MENU_ITEMS[index]
    print(f"You selected: {selected_item}\n")

    # Example: if last menu item is "Exit program", exit the script
    if index == len(MENU_ITEMS) - 1:
        print("Exiting program...")
        GPIO.cleanup()
        sys.exit(0)
    else:
        print("Performing action... (stub)")
        time.sleep(1.5)  # Simulate some work
        # After action, redraw menu
        global menu_needs_redraw
        with lock:
            menu_needs_redraw = True


def button_callback(channel):
    """
    Callback for button presses.
    This is called by RPi.GPIO in a separate context when an edge is detected.
    """
    global current_index, menu_needs_redraw

    # Small debounce delay inside callback (extra safety)
    time.sleep(0.02)

    # Only react if the button is actually pressed (active LOW)
    if GPIO.input(channel) == GPIO.LOW:
        with lock:
            if channel == BTN_UP:
                # Move selection up
                current_index = (current_index - 1) % len(MENU_ITEMS)
                menu_needs_redraw = True

            elif channel == BTN_DOWN:
                # Move selection down
                current_index = (current_index + 1) % len(MENU_ITEMS)
                menu_needs_redraw = True

            elif channel == BTN_SELECT:
                # Handle selection in a separate thread so we don't block the callback
                threading.Thread(target=handle_selection, args=(current_index,), daemon=True).start()

            # LEFT and RIGHT are currently unused, but reserved for future:
            # e.g., channel == BTN_LEFT: go back, channel == BTN_RIGHT: go into submenu
            # You can add behavior here later if needed.


def setup_gpio():
    """Configure GPIO pins and interrupts."""
    GPIO.setmode(GPIO.BCM)

    # Set buttons as inputs with internal pull-ups (so press pulls to GND)
    for pin in [BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT, BTN_SELECT]:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # Add edge detection for button presses (falling edge = press to GND)
    # bouncetime in ms to help debounce
    GPIO.add_event_detect(BTN_UP, GPIO.FALLING, callback=button_callback, bouncetime=150)
    GPIO.add_event_detect(BTN_DOWN, GPIO.FALLING, callback=button_callback, bouncetime=150)
    GPIO.add_event_detect(BTN_LEFT, GPIO.FALLING, callback=button_callback, bouncetime=150)
    GPIO.add_event_detect(BTN_RIGHT, GPIO.FALLING, callback=button_callback, bouncetime=150)
    GPIO.add_event_detect(BTN_SELECT, GPIO.FALLING, callback=button_callback, bouncetime=150)


def main():
    global menu_needs_redraw

    setup_gpio()

    try:
        # Initial draw
        print_menu()

        # Main loop: just sleep and redraw menu when needed
        while True:
            with lock:
                if menu_needs_redraw:
                    print_menu()
                    menu_needs_redraw = False

            time.sleep(0.05)  # Light idle, keeps CPU usage low

    except KeyboardInterrupt:
        # Allow Ctrl+C exit from keyboard
        print("\nKeyboard interrupt received, exiting...")
    finally:
        GPIO.cleanup()
        print("GPIO cleaned up. Bye!")


if __name__ == "__main__":
    main()
