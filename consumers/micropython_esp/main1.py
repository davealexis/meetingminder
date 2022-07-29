from machine import Pin
from utime import sleep
from network import WLAN, STA_IF, AP_IF
import lib.mrequests as requests
import ujson
import secrets

MongoUrl = 'https://data.mongodb-api.com/app/data-pvtrm/endpoint/data/beta/action/'

blueLed = Pin(16, Pin.OUT)
greenLed = Pin(5, Pin.OUT)
redLed = Pin(4, Pin.OUT)
blueLed.value(True)
greenLed.value(True)
redLed.value(True)

# .............................................................................

def flash(ledPin, duration):
    ledPin.value(False)
    sleep(duration)
    ledPin.value(True)
    sleep(duration)

# .............................................................................

def connect():
    # Ensure that the Access Point mode is disabled
    wifi = WLAN(AP_IF)
    wifi.active(False)
    
    # Fire up the station mode
    wifi = WLAN(STA_IF)
    wifi.active(True)
    wifi.connect(secrets.wifi_network, secrets.wifi_password)

    while not wifi.isconnected():
        pass

    print('Connected')

# .............................................................................

def getEvents():
    req = '{ "dataSource": "ClusterOne", "database": "notifications", "collection": "events", "filter": {}, "projection": { "_id": 0, "title": 1, "startTime": 1 } }'
    headers = {
        b'Content-Type': b'application/json',
        b'Access-Control-Request-Headers': b'*',
        b'api-key': b'Dgxmc35QxTH1aUL14LZEfsjR2Epb74XZfef7397XEPuCvMHiIT2baIroutVdJAg1',
        b'Connection': b'close'
    }

    resp = requests.post(MongoUrl + "find", data=req, headers=headers)
    nextEvent = {}

    if resp.status_code == 200:
        if len(resp.text) > 0:
            doc = ujson.loads(resp.text)

            if doc.get("documents"):
                events = doc["documents"]

                if len(events):
                    print("Events:")
                    for event in events:
                        print(event)
                else:
                    print("No events today")
            elif doc.get("document"):
                event = doc["document"]
                nextEvent['title'] = event['title']
                nextEvent['time'] = event['startTime']

                print(nextEvent)
        else:
            print("No meetings today")
    else:
        print("Error: ", resp.status_code, " :: ", resp.reason)


# .............................................................................

def run():
    connect()
    getEvents()

# .............................................................................

run()