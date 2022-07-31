import json
import httpx
import pendulum
from win32com.client import Dispatch as ComDispatch
import asyncio


MongoUrl = 'https://data.mongodb-api.com/app/data-pvtrm/endpoint/data/beta/action/'

"""
    What to do:
    - Fetches events from MongoDB
    - Announce when the next meeting will be. If the meeting list is empty,
      announce that there are no meetings today.
    - Fire up background tasks
        - Task 1: Get the next event and wait for time to start notifications.
        - Task 2: Occasionally fetch events
            - Check if we're within "do not disturb" time (weekends, nights, etc)
              If so, don't do anything.
            - Active time ranges are defined in the config file.
        - Task 3: Manage user input
            - Control-C to exit
            - Skip next meeting
            - Force refresh
            - Announce when next meeting will be
"""


# -----------------------------------------------------------------------------
class MeetingMinder():

    # -------------------------------------------------------------------------
    def __init__(self):
        self.speaker = ComDispatch("SAPI.SpVoice")
        self.events = []

    
    # -------------------------------------------------------------------------
    async def run(self):
        """
            Start background tasks
        """

        asyncio.create_task(self.eventRefresherTask())
        asyncio.create_task(self.eventSchedulerTask())

    # -------------------------------------------------------------------------
    async def eventRefresherTask(self):
        while True:
            print("Refreshing events...")

            events = await self.getEvents()
            nextEvent = [e for e in self.events if e['status'] == 'scheduled']
            
            if nextEvent:
                nextEvent = nextEvent[0]
            else:
                nextEvent = events[0]

            events = [e for e in events if not (nextEvent and e['time'] != nextEvent['time'])]
            self.events = [nextEvent, *events]

            if len(self.events) and self.events[0]['status'] == 'pending':
                nextEvent = self.events[0]
                nextEvent['status'] = 'scheduled'
                asyncio.create_task(self.announce(nextEvent))

            await asyncio.sleep(60)

    # -------------------------------------------------------------------------
    async def eventSchedulerTask(self):
        while True:
            if not self.events:
                print("Waiting...")
                await asyncio.sleep(1)
                continue

            nextEvent = self.events[0]
            
            print(f"Next event is {nextEvent['title']} at {nextEvent['time'].format('h:mm A')}")

            if nextEvent['status'] == 'pending':
                nextEvent['status'] = 'scheduled'
                asyncio.create_task(self.announce(nextEvent))

            await asyncio.sleep(10)

    # -------------------------------------------------------------------------
    async def announce(self, event):
        """
            Wait for the configured time before the event starts, then start
            announcing the event.
            Exit when the event is done.
        """
        eventTime = event["time"]
        eventTitle = event["title"]

        timeUntilEvent = pendulum.now().diff(eventTime)
        self.speaker.speak(f"Your next meeting is {eventTitle} in {timeUntilEvent.in_words()} at {eventTime.format('h:mm A')}")

        while True:
            """
                We don't need to spin our wheels fast if the event is a relatively long
                time in the future. We can go to sleep for a long time, and wake up to
                check every now and then.
                When the meeting is 5 minutes out, we can start the announcement cyvle.
            """

            sleepTime = await self.timeToWait(eventTime)

            if sleepTime:
                await asyncio.sleep(sleepTime)
                continue


            timeUntilEvent = pendulum.now().diff(eventTime)

            sleepTime = 1

            if timeUntilEvent.in_minutes() <= -1:
                print("Meeting started. I'm going away.")
                self.events.pop(0)
                break
            elif timeUntilEvent.in_seconds() <= 10 and timeUntilEvent.in_seconds() >= 0:
                self.speaker.speak(f"Your meeting is starting. Please be prepared.")
                await asyncio.sleep(10)    
            elif timeUntilEvent.in_minutes() <= 1:
                self.speaker.speak(f"Your meeting starts in {timeUntilEvent.in_words()}")
            elif timeUntilEvent.in_minutes() <= 3:
                self.speaker.speak(f"Your meeting starts in {timeUntilEvent.in_words()}")
            elif timeUntilEvent.in_minutes() <= 5:
                self.speaker.speak(f"Your next meeting, {eventTitle}, is at {eventTime.format('h:mm A')}")
            elif timeUntilEvent.in_minutes() > 6:
                sleepTime = 10

            await asyncio.sleep(sleepTime)

    # -------------------------------------------------------------------------
    async def timeToWait(self, eventTime):
        timeUntilEvent = pendulum.now().diff(eventTime)

        if timeUntilEvent.in_minutes() <= 5:
            if timeUntilEvent.in_hours() > 0:
                # The meeting is more than an hour away. Sleep for an hour.
                sleepTime = 60 * 60
            elif timeUntilEvent.in_minutes() > 10:
                # The meeting is less than an hour away, but more than 10 minutes.
                sleepTime = 10 * 60
            elif timeUntilEvent.in_minutes() > 6:
                sleepTime = 10
            else:
                sleepTime = 0

            return sleepTime

    # -------------------------------------------------------------------------
    async def getEvents(self):
        req = '''{
            "dataSource": "ClusterOne",
            "database": "notifications",
            "collection": "events",
            "pipeline": [
                {
                    "$addFields": {
                        "timeDiff": {
                            "$dateDiff": {
                                "startDate": "$$NOW",
                                "endDate": "$startTime",
                                "unit": "second"
                            }
                        }
                    }
                },
                {
                    "$match": { "$expr": { "$gt": [ "$timeDiff", 0 ] } }
                },
                {
                    "$sort": { "startTime": 1 }
                },
                {
                    "$limit": 5
                },
                {
                    "$project": {
                        "_id": 0,
                        "title": 1,
                        "startTime": 1,
                        "startTicks": "$startTimestamp"
                    }
                }
            ]
        }'''

        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Request-Headers': '*',
            'api-key': 'Dgxmc35QxTH1aUL14LZEfsjR2Epb74XZfef7397XEPuCvMHiIT2baIroutVdJAg1',
            'Connection': 'close'
        }

        with httpx.Client() as client:
            resp = client.post(MongoUrl + "aggregate", data=req, headers=headers)

            eventList = []
            nextEvent = {}

            if resp.status_code == 200:
                if len(resp.text) > 0:
                    doc = json.loads(resp.text)

                    if doc.get("documents"):
                        events = doc["documents"]

                        if len(events):
                            for event in events:
                                eventList.append({
                                    "title": event["title"],
                                    "time": pendulum.parse(event["startTime"]).in_tz('America/New_York'),
                                    "status": "pending"
                                })
                        else:
                            print("No events today")
                    elif doc.get("document"):
                        event = doc["document"]
                        eventList.append({
                            "title": event["title"],
                            "time": pendulum.parse(event["startTime"]).in_tz('America/New_York'),
                            "status": "pending"
                        })

                        eventList.append(nextEvent)
                else:
                    self.speaker.Speak("No more meetings today! WOO HOO!")
            else:
                print("Error: ", resp.status_code, " :: ", resp.text)

            for e in eventList:
                print(e)

            return [e for e in eventList if e["time"] > pendulum.now()]


# -----------------------------------------------------------------------------
async def main():
    """
        Initialize application state by fetching events from MongoDB, then
        start background tasks.
    """
    meetingMinder = MeetingMinder()
    asyncio.create_task(meetingMinder.run())
    
    while True:
        await asyncio.sleep(1)

        if asyncio.get_event_loop().is_closed():
            break


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())