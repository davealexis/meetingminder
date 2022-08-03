#include <TaskScheduler.h>
#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>
#include <ArduinoJson.h>

// #define DEBUG
// #define NEOPIXEL

#ifdef NEOPIXEL
#include <FastLED.h>
#endif

/**
 * Create a "secrets.h" file with the following contents:
 *      const char *ssid = "";
 *      const char *password = "";
 *      const char *ATLAS_API_KEY = "";
 */
#include "secrets.h"

const long NOTIFICATION_THRESHOLD_UPCOMING = -300; // 5 minutes
const long NOTIFICATION_THRESHOLD_IMMINENT = -60;  // 1 minute
const long NOTIFICATION_THRESHOLD_NOW = -10;       // 10 seconds
const long NOTIFICATION_THRESHOLD_DONE = 300;      // 5 minutes after

// Define the start and hours within which meetings are refreshed.
// Outside of these hours, the device will not refresh the meeting list, and can go to sleep.
// !! Change these values to match the appropriate UTC times for your timezone.
const int REFRESH_START_HOUR_UTC = 12; // 7amEST (12PM UTC)
const int REFRESH_END_HOUR_UTC = 1;    // 8pmEST (1AM UTC)

const char *MONGODB_QUERY PROGMEM = "{"
                                    " \"dataSource\": \"CHANGE_ME\"," // <<< Change this to the appropriate MongoDB cluster name
                                    "   \"database\": \"notifications\","
                                    "   \"collection\": \"events\","
                                    "   \"pipeline\": ["
                                    "       {"
                                    "           \"$addFields\": {"
                                    "               \"timeDiff\": {"
                                    "                   \"$dateDiff\": {"
                                    "                       \"startDate\": \"$$NOW\","
                                    "                       \"endDate\": \"$startTime\","
                                    "                       \"unit\": \"second\""
                                    "                   }"
                                    "               }"
                                    "           }"
                                    "       },"
                                    "       {"
                                    "           \"$match\": { \"$expr\": { \"$gt\": [ \"$timeDiff\", 0 ] } }"
                                    "       },"
                                    "       {"
                                    "           \"$sort\": { \"startTime\": 1 }"
                                    "       },"
                                    "       {"
                                    "           \"$limit\": 1"
                                    "       },"
                                    "       {"
                                    "           \"$project\": { \"_id\": 0, \"title\": 1, \"startTime\": 1 }"
                                    "       }"
                                    "   ]"
                                    "}";
const char *ATLAS_HOST PROGMEM = "data.mongodb-api.com";
const uint16_t ATLAS_PORT = 443;
int mongoDbQueryLength = 0;

#define LED_ON LOW
#define LED_OFF HIGH

#ifdef NEOPIXEL
    #define NUM_LEDS 1
    #define LED_PIN 5
    #define COLOR_ORDER GRB
    CRGB leds[NUM_LEDS];
#else
    // Uncomment the section of pins you want to use depending on the type of ESP8266 board you have.

    // // ESP01 module
    #define RED_LED_PIN 1
    #define GREEN_LED_PIN 2
    #define BLUE_LED_PIN 3

    // // Wemos D1 Mini
    // #define RED_LED_PIN 2
    // #define GREEN_LED_PIN 4
    // #define BLUE_LED_PIN 5

    // NodeMCU form factor board
    // #define RED_LED_PIN 13
    // #define GREEN_LED_PIN 12
    // #define BLUE_LED_PIN 14
#endif

enum Colors
{
    Red,
    Green,
    Blue,
    Yellow
};

enum EventStatus
{
    WAITING,
    NOTIFYING,
    PASSED
};

struct Event
{
    tm startTime;
    EventStatus status;
};

Event nextEvent;
bool refreshed;
bool eventIsNow;
Event tempEvent;

// --- Tasks ---

/**
 * Task: NTP tine sync
 * Description: Syncs the time with the NTP server every hour
 */
void ntpSyncTime();
Task timeSyncer(1000 * 60 * 60, TASK_FOREVER, &ntpSyncTime);

/**
 * Task: Event Fetcher
 * Description: Fetches the next event from the MongoDB
 * Interval: Every 2 minutes
 */
void fetchEvents();
Task eventFetcher(1000 * 60 * 2, TASK_FOREVER, &fetchEvents);

/**
 * Task: Event Manager
 * Description: Waits for the next event, and starts notifying the user
 *              starting from 5 minutes before the event.
 * Interval: 10 seconds
 */
void checkEvents();
Task eventManager(10 * 1000, TASK_FOREVER, &checkEvents);

/**
 * Task: Event Notifier
 * Description: Notifies the user of the next event
 * Interval: 2 seconds
 */
void notifyEvent();
Task eventNotifier(2 * 1000, TASK_FOREVER, &notifyEvent);

Scheduler taskRunner;


// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
void setup()
{
    #ifdef DEBUG
    Serial.begin(115200);
    while (!Serial)
    {
        ; // wait for serial port to connect. Needed for native USB port only
    }
    #endif

    #ifdef NEOPIXEL
    FastLED.addLeds<WS2812, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
    FastLED.setBrightness(100);
    #else
    pinMode(RED_LED_PIN, OUTPUT);
    pinMode(GREEN_LED_PIN, OUTPUT);
    pinMode(BLUE_LED_PIN, OUTPUT);
    #endif

    nextEvent.startTime = {0, 0, 0, 0, 0, 0, 0, 0, 0};
    nextEvent.status = WAITING;
    mongoDbQueryLength = strlen_P(MONGODB_QUERY);

    WiFi.mode(WIFI_STA);
    WiFi.hostname("MeetingMinder_ESP8266");
    WiFi.begin(ssid, password);

    while (WiFi.status() != WL_CONNECTED)
    {
        flashLed(Red, 250);

        #ifdef DEBUG
        Serial.print(".");
        #endif
    }

    #ifdef DEBUG
    Serial.println("");
    Serial.println("WiFi connected");
    Serial.println("IP address: ");
    Serial.println(WiFi.localIP());
    #endif

    ntpSyncTime();

    // Let the user know we're almost ready to rock.
    flashLed(Yellow, 500);
    flashLed(Yellow, 500);

    taskRunner.init();

    taskRunner.addTask(eventFetcher);
    eventFetcher.enable();

    taskRunner.addTask(eventManager);
    eventManager.enable();

    taskRunner.addTask(eventNotifier);
    eventNotifier.enable();

    // Delay the start the time syncer in 1 hour. If we start the time syncer immediately,
    // it will sync the time as soon as the task is run. Since we already sync the time from
    // the NTP server on startup, we don't want to sync the time again immediately.
    taskRunner.addTask(timeSyncer);
    timeSyncer.enableDelayed(1000 * 60 * 60);
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
void loop()
{
    taskRunner.execute();
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
void fetchEvents()
{
    #ifdef DEBUG
    Serial.println("Fetching events...");
    #endif

    time_t now;
    struct tm *timeinfo;
    time(&now);
    timeinfo = localtime(&now);

    int checkHour = timeinfo->tm_hour;
    int checkEndHour = REFRESH_END_HOUR_UTC;

    // We only want to do expensive network calls if we're within our "work day"

    // Adjust for times that cross midnight
    if (REFRESH_START_HOUR_UTC > REFRESH_END_HOUR_UTC)
    {
        if (checkHour < REFRESH_START_HOUR_UTC)
        {
            checkHour += 24;
        }

        checkEndHour += 24;
    }

    if (checkHour < REFRESH_START_HOUR_UTC || checkHour >= checkEndHour)
    {
        return;
    }

    #ifdef DEBUG
    char currentTimeStr[20];
    strftime(currentTimeStr, sizeof(currentTimeStr), "%G-%m-%dT%T", timeinfo);
    Serial.print("Current time: ");
    Serial.println(currentTimeStr);
    Serial.print(timeinfo->tm_hour);
    Serial.print(":");
    Serial.print(timeinfo->tm_min);
    Serial.print(":");
    Serial.println(timeinfo->tm_sec);
    #endif

    // Use WiFiClientSecure class to create TLS connection
    WiFiClientSecure client;
    client.setInsecure(); // the magic line, use with caution

    #ifdef DEBUG
    Serial.println("Connecting to MongoDB");
    #endif

    if (!client.connect(ATLAS_HOST, ATLAS_PORT))
    {
        #ifdef DEBUG
        Serial.println("Connection failed");
        #endif

        return;
    }

    #ifdef DEBUG
    Serial.print("Requesting data...");
    #endif

    // Make a HTTP request:
    client.println("POST /app/data-pvtrm/endpoint/data/beta/action/aggregate HTTP/1.1");
    client.println("Host: data.mongodb-api.com");

    // Headers
    client.println("Content-Type: application/json");
    client.println("Access-Control-Request-Headers: *");
    client.print("api-key: ");
    client.println(ATLAS_API_KEY);
    client.print("Content-Length: ");
    client.println(mongoDbQueryLength);
    client.println("Connection: close");
    client.println();

    yield();

    // Body
    client.print(MONGODB_QUERY);

    yield();

    #ifdef DEBUG
    Serial.println("Request sent");
    #endif

    while (client.connected())
    {
        String line = client.readStringUntil('\n');

        if (line == "\r")
        {
            #ifdef DEBUG
            Serial.println("Headers received");
            #endif

            break;
        }
    }

    #ifdef DEBUG
    Serial.println("Reading response");
    #endif

    String responseBody = client.readStringUntil('\n');

    #ifdef DEBUG
    Serial.println("Parsing response");
    #endif

    yield();

    StaticJsonDocument<512> documents;
    DeserializationError err = deserializeJson(documents, responseBody);

    yield();

    if (documents.containsKey("documents"))
    {
        JsonVariant events = documents["documents"].as<JsonVariant>();

        if (events.size() > 0)
        {
            // We're expecting just the one "next" event. If we change our approach to
            // get a list of events, we'll need to change this to loop over the results.
            JsonVariant event = events[0];
            const char *title = event["title"];
            const char *startTime = event["startTime"];

            #ifdef DEBUG
            Serial.print(title);
            Serial.print(" :: ");
            Serial.println(startTime);
            #endif

            tm eventStartTime = parseTime(startTime);

            yield();

            if (compareTimes(eventStartTime, nextEvent.startTime) != 0)
            {
                // Don't update if nextEvent is currently being nofified. Cache the update
                // and use it after the notification period completes
                if (nextEvent.status == NOTIFYING)
                {
                    #ifdef DEBUG
                    Serial.println("Caching event");
                    #endif

                    tempEvent.startTime = eventStartTime;
                    refreshed = true;
                }
                else
                {
                    nextEvent.startTime = eventStartTime;
                }
            }

            #ifdef DEBUG
            Serial.println("-------------------------");
            #endif
        }
        #ifdef DEBUG
        else
        {
            Serial.println("No events found");
        }
        #endif
    }
    #ifdef DEBUG
    else
    {
        Serial.println("No events found");
    }
    #endif

    client.stop();
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
void checkEvents()
{
    // Update the nextEvent with the updated event data if an update happened
    // while we were in our notification period.
    if (nextEvent.status == WAITING && refreshed)
    {
        #ifdef DEBUG
        Serial.println("Refreshing event that was updated during notification period");
        #endif

        nextEvent.startTime = tempEvent.startTime;
        refreshed = false;
    }

    // Check if the next event is within the next 5 minutes. If so, start
    // the countdown and notifying the user with LEDs.
    time_t now = time(nullptr);
    time_t eventTime = mktime(&nextEvent.startTime);
    long timeDiff = long(difftime(now, eventTime));

    if (timeDiff < NOTIFICATION_THRESHOLD_UPCOMING || timeDiff > NOTIFICATION_THRESHOLD_DONE + 60)
    {
        return;
    }

    if (nextEvent.status == NOTIFYING)
    {
        if (timeDiff >= NOTIFICATION_THRESHOLD_DONE)
        {
            #ifdef DEBUG
            Serial.println("The event has passed");
            #endif

            ledOff();
            nextEvent.startTime = {0, 0, 0, 0, 0, 0, 0, 0, 0};
            nextEvent.status = WAITING;
            eventIsNow = false;
        }

        return;
    }

    if (timeDiff >= NOTIFICATION_THRESHOLD_UPCOMING && timeDiff < NOTIFICATION_THRESHOLD_DONE)
    {
        // 5 minutes until the event starts. Start the countdown.
        // This is done by just setting the state to NOTIFYING, and the Task that manages
        // the LEDs will handle the rest.
        #ifdef DEBUG
        Serial.println("About to start the event");
        #endif
        nextEvent.status = NOTIFYING;
    }
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
void notifyEvent()
{
    if (nextEvent.status == WAITING)
    {
        return;
    }

    time_t eventStartTime = mktime(&nextEvent.startTime);
    long timeDiff = long(difftime(time(nullptr), eventStartTime));

    if (NOTIFICATION_THRESHOLD_NOW <= timeDiff && timeDiff < NOTIFICATION_THRESHOLD_DONE)
    {
        // Turn on red LED to let the user know they better get their arse into the meeting.
        ledOn(Red);
        eventIsNow = true;
        // delay(1000);
    }
    else if (NOTIFICATION_THRESHOLD_IMMINENT <= timeDiff && timeDiff < NOTIFICATION_THRESHOLD_NOW)
    {
        // Flash Yellow LED to let the user know that an event is starting within 1 minute.
        // flashLed(Yellow, 150);
        // flashLed(Yellow, 150);
        ledOn(Yellow);
    }
    else if (NOTIFICATION_THRESHOLD_UPCOMING <= timeDiff && timeDiff < NOTIFICATION_THRESHOLD_IMMINENT)
    {
        // Flash green LED to let the user know that an event is starting within the next 5 minutes.
        // flashLed(Green, 500);
        ledOn(Green);
    }
    else
    {
        #ifdef DEBUG
        Serial.println("Notification done");
        #endif

        nextEvent.status = WAITING;

        // Turn off LEDs
        ledOff();
    }
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
// Parse datetime in the format: "2022-02-07T14:00:00.000Z"
tm parseTime(const char *datetime)
{
    struct tm timeinfo;
    strptime(datetime, "%Y-%m-%dT%H:%M:%S.000Z", &timeinfo);

    return timeinfo;
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
// Sync time wiht NTP server. We're not going to ask for local time, since
// UTC is perfectly fine for our needs. The Google calendar times are in UTC.
void ntpSyncTime()
{
    #ifdef DEBUG
    Serial.print("Waiting for NTP time sync: ");
    #endif

    // Set time via NTP, as required for x.509 validation
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");

    time_t now = time(nullptr);

    while (now < 8 * 3600 * 2)
    {
        #ifdef DEBUG
        Serial.print(".");
        #endif

        delay(100);
        now = time(nullptr);
    }

    struct tm timeinfo;
    gmtime_r(&now, &timeinfo);

    #ifdef DEBUG
    Serial.println("");
    Serial.print("Current time: ");
    Serial.println(asctime(&timeinfo));
    #endif
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
// Flash a given color of the RGB Neopixel for the specified duration.
// This turns the LED on with the specified color, then turns it off.
void flashLed(Colors color, int duration)
{

    ledOn(color);
    delay(duration);
    ledOff();
    delay(duration);
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
// Turns on the neopixel LED with the specified color.
void ledOn(Colors color)
{
    #ifdef NEOPIXEL
    leds[0] = CRGB(
        color == Red || color == Yellow ? 255 : 0,
        color == Green ? 255 : color == Yellow ? 250
                                               : 0,
        color == Blue ? 255 : 0);

    FastLED.show();
    #else
    digitalWrite(RED_LED_PIN, color == Red || color == Yellow ? LED_ON : LED_OFF);
    digitalWrite(GREEN_LED_PIN, color == Green || color == Yellow ? LED_ON : LED_OFF);
    digitalWrite(BLUE_LED_PIN, color == Blue ? LED_ON : LED_OFF);
    #endif
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
// Turns off the LEDs.
void ledOff()
{
    #ifdef NEOPIXEL
    leds[0] = CRGB(0, 0, 0);
    FastLED.show();
    #else
    digitalWrite(RED_LED_PIN, LED_OFF);
    digitalWrite(GREEN_LED_PIN, LED_OFF);
    digitalWrite(BLUE_LED_PIN, LED_OFF);
    #endif
}

// - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
int compareTimes(tm a, tm b)
{
    if (a.tm_hour < b.tm_hour || a.tm_min < b.tm_min || a.tm_sec < b.tm_sec)
    {
        return -1;
    }
    else if (a.tm_hour > b.tm_hour || a.tm_min > b.tm_min || a.tm_sec > b.tm_sec)
    {
        return 1;
    }
    else
    {
        return 0;
    }
}
