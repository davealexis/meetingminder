from machine import Pin
import time

# .............................................................................
class LedFlasher():

    # .........................................................................
    def __init__(self, red_pin, green_pin, blue_pin):
        self.blueLed = Pin(blue_pin, Pin.OUT)
        self.greenLed = Pin(green_pin, Pin.OUT)
        self.redLed = Pin(red_pin, Pin.OUT)

        self.blueLed.value(True)
        self.greenLed.value(True)
        self.redLed.value(True)

        self.Red = [self.redLed]
        self.Green = [self.greenLed]
        self.Blue = [self.blueLed]
        self.Yellow = [self.redLed, self.greenLed]

        self.LedOn = False
        self.LedOff = True

    # .........................................................................
    def flash(self, color, duration):
        self.redLed.value(self.LedOff)
        self.greenLed.value(self.LedOff)
        self.blueLed.value(self.LedOff)

        for led in color:
            led.value(self.LedOn)

        time.sleep(duration)

        for led in color:
            led.value(self.LedOff)

        time.sleep(duration)

    # .........................................................................
    def on(self, color):
        self._off()

        for led in color:
            led.value(self.LedOn)
            time.sleep_ms(1)

    # .............................................................................
    async def off(self):
        self.redLed.value(self.LedOff)
        self.greenLed.value(self.LedOff)
        self.blueLed.value(self.LedOff)
        time.sleep_ms(1)