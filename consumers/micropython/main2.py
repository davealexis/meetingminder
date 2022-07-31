from network import WLAN, STA_IF, AP_IF
import sys
import uasyncio as asyncio
import secrets
from meetingminder import MeetingMinder
from leds import LedFlasher

# MicroPython on the Raspberry Pi Pico W does not have the ntptime module
if sys.platform != 'rp2':
    import ntptime


# .............................................................................
def connect(leds):
    leds._on(leds.Red)

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
    leds.flash(leds.Green, 0.2)
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
    leds = LedFlasher(red_pin=4, green_pin=5, blue_pin=16)     # <-- ESP8266
    # leds = LedFlasher(red_pin=23, green_pin=22, blue_pin=21)   # <-- ESP32
    # leds = LedFlasher(red_pin=18, green_pin=19, blue_pin=20)   # <-- RPi Pico W

    print("Connecting to network...")
    connect(leds)

    if sys.platform != 'rp2':
        print("Syncing time from NTP server...")

        while True:
            try:
                leds.flash(leds.Yellow, 0.2)
                ntptime.settime()
                break
            except:
                ...

    print("Starting up")
    leds._on(leds.Green)

    try:
        asyncio.run(main(leds))
    except:
        asyncio.new_event_loop()
