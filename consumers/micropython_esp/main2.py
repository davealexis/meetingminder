from machine import Pin
from network import WLAN, STA_IF, AP_IF
import ntptime
import utime as time
import urequests as requests
import uasyncio as asyncio
import secrets
from meetingminder import MeetingMinder


# .............................................................................
class LedFlasher():

    # .........................................................................
    def __init__(self):
        self.blueLed = Pin(16, Pin.OUT)
        self.greenLed = Pin(5, Pin.OUT)
        self.redLed = Pin(4, Pin.OUT)
        
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
    async def ledOn(self, color):
        self.ledOff()

        for led in color:
            led.value(self.LedOn)

    # .............................................................................
    def ledOff(self):
        self.redLed.value(self.LedOff)
        self.greenLed.value(self.LedOff)
        self.blueLed.value(self.LedOff)


# .............................................................................
def connect(leds):
    leds.flash(leds.Red, 0.2)

    # Ensure that the Access Point mode is disabled
    wifi = WLAN(AP_IF)
    wifi.active(False)
    
    # Fire up the station mode and connect to the network
    wifi = WLAN(STA_IF)
    wifi.active(True)
    wifi.connect(secrets.wifi_network, secrets.wifi_password)

    while not wifi.isconnected():
        leds.flash(leds.Red, 0.5)

    # We're connected to WiFi! Let's go!
    leds.flash(leds.Yellow, 0.2)
    leds.flash(leds.Yellow, 0.2)
    leds.flash(leds.Yellow, 0.2)


# .............................................................................

def set_global_exception():
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
        
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)
    

# .............................................................................

async def main(leds):
    """
        Initialize application state by fetching events from MongoDB, then
        start background tasks.
    """
    set_global_exception()
    
    meetingMinder = MeetingMinder(leds)
    asyncio.create_task(meetingMinder.run())
    
    while True:
        await asyncio.sleep(1)

# .............................................................................

if __name__ == "__main__":
    leds = LedFlasher()

    print("Connecting to network...")
    connect(leds)
    
    print("Syncing time from NTP server...")
    
    while True:
        try:
            leds.flash(leds.Yellow, 0.2)
            ntptime.settime()
            break
        except:
            ...
    
    leds.flash(leds.Green, 1)
    print("Starting up")
    
    try:
        asyncio.run(main(leds))
    except:
        asyncio.new_event_loop()
