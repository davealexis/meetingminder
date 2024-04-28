import time
import board
import neopixel
import supervisor

led = neopixel.NeoPixel(board.NEOPIXEL, 4)
color = None
ledsOn = False
maxBrightness = 100
countdown = 600

while True:
    if supervisor.runtime.serial_bytes_available:
        color = input().strip()

    if color == "red":
        ledsOn = True

        for value in range(0, maxBrightness, 5):
            led.fill((value, 0, 0))

        time.sleep(1)

        for value in range(maxBrightness, 0, -1):
            led.fill((value, 0, 0))

        time.sleep(.25)
    elif color == "green":
        ledsOn = True

        for value in range(0, maxBrightness, 5):
            led.fill((0, value, 0))
            time.sleep(0.01)

        time.sleep(.5)

        for value in range(maxBrightness, 0, -1):
            led.fill((0, value, 0))
            time.sleep(0.01)

        time.sleep(.25)
    elif color == "blue":
        ledsOn = True
        led.fill((0, 0, maxBrightness))
    elif color == "yellow":
        ledsOn = True

        for value in range(0, maxBrightness, 5):
            led.fill((value, value, 0))

        time.sleep(.25)

        for value in range(255, 0, -1):
            led.fill((value, value, 0))

        time.sleep(.25)
    else:
        if ledsOn:
            led.fill((0, 0, 0))
            ledsOn = False
