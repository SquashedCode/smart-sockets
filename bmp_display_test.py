import os
import sys
import logging

EPD_PATH = os.path.join(os.path.dirname(__file__), "e-Paper/RaspberryPi_JetsonNano/python/lib/")
if os.path.exists(EPD_PATH):
	sys.path.append(EPD_PATH)
else:
	print(f"EPD library path not found: %s",EPD_PATH)
	sys.exit(1)

from waveshare_epd import epd4in2_V2
from PIL import Image

logging.basicConfig(level=logging.INFO)

""" Function to load a bmp image and display on e-Paper display 		"""
""" Params: path : string							"""
""" Required Libraries : from waveshare_epd import ... , from PIL import Image 	"""

def display_bmp_img(path):
	logging.info("Loading BMP image...")
	# Clear the display
	epd.Clear()
	# Open image from filepath
	image = Image.open(bmp_path)
	# Convert image to monochrome
	image = image.convert("1")
	# Resize image to match epd display
	image = image.resize((epd.width, epd.height))
	# Display image
	epd.display(epd.getbuffer(image))

""" Function to load a bmp image and display on e-Paper display 		"""
""" Params: path : string							"""
""" Required Libraries : from waveshare_epd import ... , from PIL import Image 	"""

def display_bmp_img(path):
	logging.info("Loading BMP image...")
	# Clear the display
	epd.Clear()
	# Open image from filepath
	image = Image.open(bmp_path)
	# Convert image to monochrome
	image = image.convert("1")
	# Resize image to match epd display
	image = image.resize((epd.width, epd.height))
	# Display image
	epd.display(epd.getbuffer(image))
""" Function to load a bmp image and display on e-Paper display 		"""
""" Params: path : string							"""
""" Required Libraries : from waveshare_epd import ... , from PIL import Image 	"""

def display_bmp_img(path):
	logging.info("Loading BMP image...")
	# Clear the display
	epd.Clear()
	# Open image from filepath
	image = Image.open(bmp_path)
	# Convert image to monochrome
	image = image.convert("1")
	# Resize image to match epd display
	image = image.resize((epd.width, epd.height))
	# Display image
	epd.display(epd.getbuffer(image))


def main():
	if len(sys.argv) < 2:
		print(f"Usage: python3 display_bmp.py <image.bmp>")
		sys.exit(1)

	bmp_path = sys.argv[1]
	if not os.path.isfile(bmp_path):
		print("BMP file not found:", bmp_path)
		sys.exit(1)

	logging.info("Initializing display...")
	epd = epd4in2_V2.EPD()
	epd.init()
	epd.Clear()

	logging.info("Loading BMP image...")
	image = Image.open(bmp_path)

	# Convert to monochrome (Required for E-Ink e-Paper display)
	image = image.convert("1")

	# Resize your image automatically to the 4.2 resolution (400x300)
	image = image.resize((epd.width, epd.height))

	logging.info("Displaying Image...")
	epd.display(epd.getbuffer(image))

	logging.info("Putting display to sleep...")
	epd.sleep()

if __name__ == "__main__":
	main()
