"""
    Adafruit NeoPixel Trinkey notifier
"""

import time
import board
import neopixel
import supervisor
import touchio


# .............................................................................
def updateBrightness(make_brighter):
    global maxBrightness

    led.fill((0, 0, 0))

    if make_brighter:
        maxBrightness = maxBrightness = maxBrightness + 10 if maxBrightness <= 245 else 255

        for i in range(3, -1, -1):
            led[i] = (0, maxBrightness, 0)
            led.show()
            time.sleep(0.1)
        led.fill((0, 0, 0))
    else:
        maxBrightness = maxBrightness = maxBrightness - 10 if maxBrightness >= 20 else 10

        for i in range(4):
            led[i] = (maxBrightness, 0, 0)
            led.show()
            time.sleep(0.1)
        led.fill((0, 0, 0))


# .............................................................................
upButton = touchio.TouchIn(board.TOUCH2)
downButton = touchio.TouchIn(board.TOUCH1)

led = neopixel.NeoPixel(board.NEOPIXEL, 4)
color = None
ledsOn = False
maxBrightness = 100


while True:
    if supervisor.runtime.serial_bytes_available:
        color = input().strip()

    if upButton.value:
        updateBrightness(True)

    if downButton.value:
        updateBrightness(False)

    if color == "red":
        ledsOn = True
        led.fill((maxBrightness, 0, 0))
    elif color == "green":
        ledsOn = True
        led.fill((0, maxBrightness, 0))
    elif color == "blue":
        ledsOn = True
        led.fill((0, 0, maxBrightness))
    elif color == "yellow":
        ledsOn = True
        led.fill((maxBrightness, maxBrightness, 0))
    else:
        if ledsOn:
            led.fill((0, 0, 0))
            ledsOn = False

