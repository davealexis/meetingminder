# MeetingMinder - MicroPython Version

This code has been tested on the following devices:
- ESP32
- ESP8266 - NodeMCU form factor
- Wemos D1 Mini (ESP8266)
- Raspberry Pi Pico W

## Setup

1. Ensure that your LED(s) are properly wired up, and the red, green, and blue pins are specified in the LedFlasher instantiation on line 62.
2. Copy the led.py, main.py, secrets.py, meetingminder.py, and test_connectivity.py files to your board.
3. Edit the `secrets.py` file and replace the values for your network credentials, MongoDB Atlas API key, and cluster name.
4. Open the `test_connectivity.py` file and run it. If your secrets were correctly entered, you should see a list of events that were fetched from MongoDB.

The `main.py` file contains the entrypoint for the application. MicroPython will automatically look for, and execute, the main.py file on startup, so you
won't have to manually run it. Reboot your board, and the code should automatically run.