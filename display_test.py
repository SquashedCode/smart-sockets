import sys
import os
import time
import threading
import logging
import traceback

import RPi.GPIO as GPIO

# -----------------------------------------
# WAVESHARE IMPORT & PATH BUILDING
# -----------------------------------------

# Build path to Waveshare driver folder
BASE_DIR = os.path.dirname(__file__)

# Path to Waveshare lib/ (for waveshare_epd)
LIB_PATH = os.path.join(BASE_DIR, "e-Paper/RaspberryPi_JetsonNano/python/lib")

# Path to Waveshare pic/ (for Font.ttc, bmp images, etc.)
PIC_PATH = os.path.join(BASE_DIR, "e-Paper/RaspberryPi_JetsonNano/python/pic")

# Make sure python can import the waveshare library
if os.path.exists(LIB_PATH):
	sys.path.append(LIB_PATH)
else:
	logging.warning("LIB_PATH does not exist: %s", LIB_PATH)

# Import the e-paper driver
from waveshare_epd import epd4in2_V2
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO)

# ----------------------------------------
# GPIO Pin Assignments (BCM Numbering)
# ----------------------------------------

BTN_UP  = 5	# Up Button
BTN_DWN = 6	# Down Button
BTN_LFT = 13	# Left Button
BTN_RGT = 19	# Right Button
BTN_SEL = 26	# Select Button

# ----------------------------------------
# MENU ITEMS
# ----------------------------------------

MENU_ITEMS = [
	"Option 1 - Do something",
	"Option 2 - Do something else",
	"Option 3 - Another Action",
	"Option 4 - Yet another action",
	"Option 5 - Exit Program"
]

# ----------------------------------------
# STATE LOCKING CODE / SHARED VARS
# ----------------------------------------

# Menu Related Global Variables

current_index = 0
menu_needs_redraw = True
lock = threading.Lock()
current_screen = "menu"

# e-Paper Global Variables

epd = None
font_title = None
font_menu = None
Limage = None
draw = None

# ----------------------------------------
# E-PAPER HELPER FUNCTIONS <- IMPORTANT
# ----------------------------------------
def init_display():
	""" Initialize the e-Paper display, image buffer, and fonts."""
	global epd, font_title, font_menu, Limage, draw

	logging.info("Initializing 4.2\" e-Paper Display...")
	epd = epd4in2_V2.EPD()
	epd.init_fast(epd.Seconds_1_5S) # fast refresh rate
	epd.Clear()

	# Load Fonts (ADJUST FONT SIZES HERE)
	font_title = ImageFont.truetype(os.path.join(PIC_PATH, 'Font.ttc'), 24)
	font_menu = ImageFont.truetype(os.path.join(PIC_PATH, 'Font.ttc'), 18)

	# Image Instantiation - Vertical <- Change this to Horizontal potentially.
	Limage = Image.new('1', (epd.width, epd.height), 255) # 255 = white
	draw = ImageDraw.Draw(Limage)

	logging.info("Display init complete.")

def clear_display():
	""" Clear the e-Paper buffer to white """
	global Limage, draw
	draw.rectangle((0, 0, epd.width, epd.height), fill=255)

def display_bmp_file(path):
	

def draw_menu():
	""" Draw the menu onto the e-paper buffer based on current_index. """
	global current_index, Limage, draw

	clear_display()

	# Title & Instructions
	y = 4
	draw.text((10, y), "Button Menu", font = font_title, fill=0)
	y += 28
	draw.text((10, y), "Up/Down = move, Select = choose", font = font_menu, fill = 0)
	y += 24

	# Draw each menu item
	for i, item in enumerate(MENU_ITEMS):
		prefix = "> " if i == current_index else "  "
		draw.text((10, y), prefix + item, font=font_menu, fill=0)
		y += 22 # line spacing; tweak as needed

def show_selection_screen(index):
	""" Draw a 'You selected ...' screen. """
	global current_index, Limage, draw

	clear_display()
	selected_item = MENU_ITEMS[index]

	y = 30
	draw.text((10,y), "You selected:", font=font_title, fill=0)
	y +=30
	# Wrap long text if needed; for now, just draw directly:
	draw.text((10, y), selected_item, font=font_menu, fill=0)

def refresh_full():
	"""Send the current buffer to the display using a fast full refresh. """
	epd.display_Fast(epd.getbuffer(Limage))

def shutdown_display(clear_to_white : bool = True):
	"""Optional final cleanup function to clear the display"""
	try:
		epd.init()
		epd.sleep()
	except Exception as e:
		logging.warning("Error during display shutdown: %s", e)

# ----------------------------------------
# MENU LOGIC
# ----------------------------------------

def handle_selection(index):
	"""
	Handle what happens when a user presses SELECT on a given menu item.
	This will draw to the e-paper
	"""
	global current_screen, menu_needs_redraw
	selected_item = MENU_ITEMS[index]

	# Draw selection screen on e-Paper
	with lock:
		current_screen = "selection"
		show_selection_screen(index)
		refresh_full()

	# if last menu item is "Exit Program", exit the script
	if index == len(MENU_ITEMS) - 1:
		clear_display()
		draw.text((10, 10), "Exiting...", font=font_title, fill=0)
		epd.display(epd.getbuffer(Limage))
		time.sleep(1.0)
		GPIO.cleanup()
		shutdown_display(clear_to_white=True) # Blank out the panel
		logging.info("Exiting program via menu...")
		sys.exit(0)
	else:
		# Simulate doing some work ?
		logging.info("Performing action for: %s", selected_item)
		time.sleep(1.5)

		# After action, redraw menu
		with lock:
			current_screen = "menu"
			menu_needs_redraw = True

def button_callback(channel):
	"""
	Callback for button pressess (GPIO edge detect)
	"""
	global current_index, menu_needs_redraw

	# Small debounce inside callback
	time.sleep(0.02)

	# Only react if actually pressed (active LOW)
	if GPIO.input(channel) == GPIO.LOW:
		with lock:
			if channel == BTN_UP:
				current_index = (current_index - 1) % len(MENU_ITEMS)
				menu_needs_redraw = True

			elif channel == BTN_DWN:
				current_index = (current_index + 1) % len(MENU_ITEMS)
				menu_needs_redraw = True

			elif channel == BTN_SEL:
				# Launch selection ahndler in a separate thread
				threading.Thread(
					target=handle_selection,
					args=(current_index,),
					daemon=True
					).start()
			#elif channel == BTN_LFT:
			#elif channel == BTN_RGT:
			# LEFT AND RIGHT RESERVED FOR FUTURE IMPLEMENTATION

# ----------------------------------------
# GPIO SETUP AND MAIN LOOP
# ----------------------------------------

def setup_gpio():
	"""Configure GPIO pins and interrupts."""
	GPIO.setmode(GPIO.BCM)

	for pin in [BTN_UP, BTN_DWN, BTN_LFT, BTN_RGT, BTN_SEL]:
		GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

	GPIO.add_event_detect(BTN_UP, GPIO.FALLING,
				callback=button_callback, bouncetime=150)
	GPIO.add_event_detect(BTN_DWN, GPIO.FALLING,
				callback=button_callback, bouncetime=150)
	GPIO.add_event_detect(BTN_LFT, GPIO.FALLING,
				callback=button_callback, bouncetime=150)
	GPIO.add_event_detect(BTN_RGT, GPIO.FALLING,
				callback=button_callback, bouncetime=150)
	GPIO.add_event_detect(BTN_SEL, GPIO.FALLING,
				callback=button_callback, bouncetime=150)

def main():
	global menu_needs_redraw

	try:
		init_display()
		setup_gpio()

		# Initial draw
		with lock:
			current_screen = "menu"
			draw_menu()
			refresh_full()
			menu_needs_redraw=False

		# Main Loop: sleep and redraw when needed
		while True:
			with lock:
				if current_screen == "menu" and menu_needs_redraw:
					draw_menu()
					refresh_full()
					menu_needs_redraw = False

	except KeyboardInterrupt:
		logging.info("Keyboard interrupt received, exiting...")
		epd.Clear()
		GPIO.cleanup()
	finally:
		try:
			epd.sleep()
		except Exception:
			GPIO.cleanup()
			logging.info("GPIO cleaned up. Bye!")

if __name__ == "__main__":
	main()
