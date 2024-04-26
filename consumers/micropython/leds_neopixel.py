from machine import Pin
import time
import machine, neopixel
from machine import Pin

# .............................................................................
class LedFlasher():

    # .........................................................................
    def __init__(self, neopixel_pin):
        self.pixels = neopixel.NeoPixel(Pin(neopixel_pin), 1)
        self.numberOfPixels = self.pixels.n
        
        self.Red = (255, 0, 0)
        self.Green = (0, 255, 0)
        self.Blue = (0, 0, 255)
        self.Yellow = (255, 255, 0)
        self.Off = (0, 0, 0)
        
        self.off()
        
    # .........................................................................
    def set_color(self, color):
        for p in range(self.numberOfPixels):
            self.pixels[p] = color

    # .........................................................................
    def flash(self, color, duration):
        self.on(color)
        time.sleep(duration)
        self.on(self.Off)
        time.sleep(duration)

    # .........................................................................
    def on(self, color):
        self.off()
        
        for p in range(self.numberOfPixels):
            self.pixels[p] = color
            time.sleep_ms(1)
        
        self.pixels.write()

    # .............................................................................
    def off(self):
        for p in range(self.numberOfPixels):
            self.pixels[p] = self.Off
            time.sleep_ms(1)
        
        self.pixels.write()