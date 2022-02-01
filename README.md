# Meeting Minder



I created this project because I had a tendency to be late to meetings or totally miss them because I would get hyper-focused on some piece of cool code and totally forget about meetings.

The basic design is to have bright, annoying LEDs notify me when meetings are imminent. There are three components to the project:

1. Publisher: A Google App Script project that reads the next 24 hours of meetings and send them to a MongoDB collection
2. Data Store: A MongoDB Atlas collection that holds the list of events. Since the set of events is always going to be very small, we'll fit nicely within the Atlas free tier.
3. Consumer: The "client", which reads the meeting data from MongoDB and flashes RGB LEDs to indicate when a meeting was about to happen.



## Notifications

- From 5 minutes to 1 minute before the event start time: Green LED flashes with 500ms pulses.
- From 1 minute down to the event time: Yellow LED flashes with 150ms pulses.
- from 10 seconds before to 5 minutes after the time of the event:  Red LED will be turned on.
