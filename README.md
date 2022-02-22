# Meeting Minder



I created this project because I had a tendency to be late to meetings or totally miss them because I would get hyper-focused on some piece of cool code and totally forget about meetings.

The basic design is to have bright, annoying LEDs notify me when meetings are imminent. There are three components to the project:

1. Publisher: A Google App Script project that reads the next 24 hours of meetings and send them to a MongoDB collection
2. Data Store: A MongoDB Atlas collection that holds the list of events. Since the set of events is always going to be very small, we'll fit nicely within the Atlas free tier.
3. Consumer: The "client", which reads the meeting data from MongoDB and flashes RGB LEDs to indicate when a meeting was about to happen.

I created a few different versions of MeetingMinder, because.. why not? 

The first version is written in **Go and runs on a Raspberry Pi Zero W.** Go's concurrency features were ideal for this application, since there can be different concurrent tasks (each in its own Goroutine) to manage specific aspects of the functionality - periodically fetching updated meeting list, determining when the next meeting is and waiting till it's time to notify the user, and the user notifications themselves.

Then I created an **ESP8266 version that runs on a tiny ESP 01** module that is smaller than a postage stamp. The code running on the ESP8266 does basically the same thing as the Go version on the Raspberry Pi, except it is written in C/C++ (Arduino). The entire circuit board (with the ESP 01, custom power supply, and RGB LED) all fit nicely within the enclosure shown below. This is actually the frosted top of a dead LED floodlight that I re-purposed.

![Meeting Minder](https://github.com/davealexis/meetingminder/blob/main/images/Meeting%20Minder.png)

The downside of the ESP8266 is that the lack of true multitasking. Even though the code uses the TaskScheduler library to implement concurrent tasks, the library implements cooperative multitasking. This means that each task must voluntarily yield control to other tasks. What's the problem with this? Well, if the task responsible for blinking the LED in pulses of specific durations (e.g. once every 500 milliseconds) is interrupted by the task that fetches updated meetings, the blinking will stutter or stop while the lengthy, blocking operation of calling a REST API and waiting for the result is in flight. I get around this by preventing meeting refreshes during a meeting notification cycle. This is not really a big deal, since the only time it would make sense to have a meeting update while the user is being notified of an upcoming meeting is if that meeting was cancelled at the last minute.

The last version of MeetingMinder that I implemented uses an **ESP32 board**. while this is much larger than an ESP 01 board (but smaller than a Raspberry Pi Zero), the ESP32 contains a fast dual-core processor that supports [RTOS](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/freertos.html) (real-time OS). In fact, the Arduino ESP32 SDK is built on top of FreeRTOS! What's the big deal about this? The ESP32 can achieve true concurrency and even parallel processing (since tasks can run at the same time on multiple cores) and no additional libraries are required. The ESP32 version of MeetingMinder implements a number of concurrent tasks that are smoothly managed by the FreeRTOS core:

- The ESP32 has a high-precision real-time clock, meaning that it is pretty good at keeping accurate time (pretty important for keeping track of meetings). But to ensure that the clock is always set to the correct current time, a Task fires off every hour to [sync the clock with NTP](https://lastminuteengineers.com/esp32-ntp-server-date-time-tutorial/) (network time protocol) from the Internet. It might be overkill to do this every hour. Once a day should be fine.
- Every 2 minutes, another Task makes a REST call to MongoDB Atlas to fetch the next meeting. I decided not to fetch a list of meetings, since MeetingMinder's simple LED-based interface doesn't really care about anything but the very next meeting. This limits the amount of data being fetched over the Internet into this tiny device. The refresh interval is 2 minutes so that we can catch last-minute meetings that get added to the calendar.
- Every 10 seconds. another Task checks the current time against the start time of the next upcoming meeting. If the meeting is starting within the next 5 minutes, a new, dynamic Task is created to manage the LED notifications and count down to the meeting start time.
- The dynamic Task that manages the notifications only lives as long as it is doing it's thing. Then it dies. Its job is to blink the green LED at the 5 minute mark, the yellow LED at the 1 minute mark, and the red LED at the 10 second mark.

The code for these 3 versions can be seen in [/consumers](https://github.com/davealexis/meetingminder/tree/main/consumers) folder of the code repository.



## Notifications

- From 5 minutes to 1 minute before the event start time: Green LED flashes with 500ms pulses.
- From 1 minute down to the event time: Yellow LED flashes with 150ms pulses.
- from 10 seconds before to 5 minutes after the time of the event:  Red LED will be turned on.



## Failed Attempts

I had initially intended to implement MeetingMinder on an ESP8266 or ESP32 board using MicroPython. MicroPython has excellent WiFi and concurrency support on the ESP32. This might sound strange, since Python's threading and concurrency are hampered by the GIL (global interpreter lock) that ensures that only one thread is only actually running at a time. But there is no GIL in MicroPython! So it can actually run 2 parallel operations (one on each core) on an ESP32! The problem I encountered was the REST call to MongoDB failed due to the `urequests` library only supporting HTTP 1.0. The MongoDB Atlas Data API requires at least HTTP 1.1 support. Bummer.

TinyGo was a non-starter for me since it has no support for WiFi on ESP chips.

Since it seemed like I was not having any luck with using my favorite IoT boards, I decided to implement the first version on the Raspberry Pi Zero W with Go.
