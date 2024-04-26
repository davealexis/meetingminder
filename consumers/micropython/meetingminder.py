from sys import platform
import aiohttp
import asyncio
import json as json
import time
import secrets

# MicroPython's time module works on like Unix epoch time (Jan 1, 1970), except
# that it starts at Jan 1, 2000 instead. We need to adjust timestamps we receive
# from MongoDB to be compatible with the time module by deducting the MicroPython
# epoch from the incoming timestamps.
MPEpochOffset = 0 if platform == 'rp2' else 946702800


# .............................................................................
class MeetingMinder():

    # .........................................................................
    def __init__(self, ledFlasher):
        self.leds = ledFlasher
        self.events = []

        # self.leds.on(self.leds.Green)
        self.get_timezone_offset()

        # print("Epoch Offset:", MPEpochOffset)

        self.Query = '''{
            "dataSource": "''' + secrets.mongo_cluster_name + '''",
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

        self.QueryHeaders = {
            'Content-Type': 'application/json',
            'Access-Control-Request-Headers': '*',
            'api-key': secrets.mongo_api_key,
            'Connection': 'close'
        }

    # .........................................................................
    @property
    def now(self):
        if platform == 'rp2':
            return time.mktime(time.localtime())
        else:
            return time.mktime(time.localtime()) + self.utc_offset_seconds

    # .........................................................................
    async def run(self):
        """
            Start background event fetcher and scheduler tasks.
        """

        asyncio.create_task(self.event_refresher_task())
        asyncio.create_task(self.event_scheduler_task())
        asyncio.create_task(self.event_notifier_task())

    # .........................................................................
    async def event_refresher_task(self):
        """
            Periodically fetch the list of events from the MongoDB Atlas Data API.
            This method will be run as a background task, so needs to run
            forever, sleeping for a bit between fetches.
        """

        while True:
            events = await self.fetch_events()
            events_in_progress = [
                e for e in self.events if e['status'] == 'notifying']

            if events_in_progress:
                in_progress = events_in_progress[0]
                events = events_in_progress + \
                    [e for e in events if e['time'] != in_progress['time']]

            self.events = events

            # Wait for 1 minute before fetching events. We can make this longer if
            # our meeting schedule doesn't change very often.
            await asyncio.sleep(60)

    # .........................................................................
    async def event_scheduler_task(self):
        """
            Ensure that the next event in our list is being handled by a
            notification agent (yet another background task).
        """

        while True:
            if not self.events:
                # We have no meetings! Woohoo! We'll just sleep for a bit,
                # then check again until we have some.
                await asyncio.sleep(10)
                continue

            # The list of events should be sorted by time, so the first one
            # is the next meeting.
            next_event = self.events[0]

            if next_event['status'] == 'pending':
                # Make sure our next meeting gets managed by our notification
                # agent. We'll just fire up a new task to do that.
                next_event['status'] = 'scheduled'

                # print(f"Scheduled {next_event['title']}")

            await asyncio.sleep(10)

    # .........................................................................
    async def event_notifier_task(self):
        """
            Wait for the configured time before the event starts, then start
            announcing the event.
        """

        # print("Notifier started", time.localtime(self.now))
        #await self.leds.off()

        while True:
            """
                
            """

            if not self.events:
                # We have no meetings! Woohoo! We'll just sleep for a bit,
                # then check again until we have some.
                await asyncio.sleep(10)
                continue

            event = self.events[0]
            event_time = event["time"]
            # event_title = event["title"]   <-- You can use this to display the title of the event
            wait_time = 1

            now = self.now
            time_until_event = event_time - now

            # print(event_time, time.localtime(event_time), now, time.localtime(now), time_until_event)

            if time_until_event <= -120:
                self.leds.off()
                self.events.pop(0)
            elif time_until_event <= 10:          # 10 seconds before the event
                event['status'] = 'notifying'
                self.leds.off()
                self.leds.on(self.leds.Red)
            elif time_until_event <= 60:          # 1 minute before the event
                event['status'] = 'notifying'
                self.leds.on(self.leds.Yellow)
            elif time_until_event <= 180:         # 3 minutes before the event
                self.leds.on(self.leds.Green)
            elif time_until_event <= 300:         # 5 minutes before the event
                self.leds.on(self.leds.Green)
            elif time_until_event > 330:
                wait_time = 10

            await asyncio.sleep(wait_time)

    # .........................................................................
    async def fetch_events(self):
        event_list = []
        
        try:
            async with aiohttp.ClientSession(version=aiohttp.HttpVersion11) as session:
                async with session.post(secrets.mongo_url + "aggregate", data=self.Query, headers=self.QueryHeaders) as response:
                    if response.status == 200:
                        responseText = await response.text()
                        
                        if len(responseText) > 0:
                            doc = json.loads(responseText)

                            if doc.get("documents"):
                                events = doc["documents"]

                                if len(events):
                                    for event in events:
                                        if platform == 'rp2':
                                            event_time = int(
                                                event["startTicks"]) + self.utc_offset_seconds
                                        elif platform == 'esp32':
                                            event_time = int(
                                                event["startTicks"]) - MPEpochOffset + self.dst_offset_seconds
                                        else:
                                            event_time = int(
                                                event["startTicks"]) - MPEpochOffset + self.dst_offset_seconds

                                        event_list.append({
                                            "title": event["title"],
                                            "time": event_time,
                                            "status": "pending"
                                        })
                            elif doc.get("document"):
                                event = doc["document"]

                                if platform == 'rp2':
                                    event_time = int(
                                        event["startTicks"]) - MPEpochOffset + self.utc_offset_seconds
                                else:
                                    event_time = int(event["startTicks"]) - MPEpochOffset

                                event_list.append({
                                    "title": event["title"],
                                    "time": event_time,
                                    "status": "pending"
                                })
                    else:
                        event_list = self.events
        except Exception as e:
            # Failed. No biggie. We'll pull the events on the next go-around.
            # print("Failed to fetch. ", e)
            return self.events

        # print("Fetched", event_list)

        timeNow = self.now
        # print(timeNow)

        return [e for e in event_list if e["time"] > timeNow]

    # .........................................................................
    def get_timezone_offset(self):
        """
            WorldTimeAPI is a cool service that provides local timezone info
            for a given location (based on our IP address).
            We'll use this info to convert from UTC to local time.
        """
        try:
            worldTimeUrl = 'http://worldtimeapi.org/api/ip'
            resp = requests.get(worldTimeUrl)

            if resp.status_code != 200:
                # Failed to fetch the local timezone info. Default to Eastern time.
                self.utc_offset_seconds = -4 * 3600
                self.dst_offset_seconds = 0
                return

            tzInfo = json.loads(resp.text)

            self.dst_offset_seconds = int(tzInfo['dst_offset'])
            hours, minutes = [int(t) for t in tzInfo['utc_offset'].split(':')]
            self.utc_offset_seconds = (
                hours * 3600) + (minutes * 60 if hours > 0 else minutes * -60)
        except:
            # Failed to fetch the local timezone info. Default to Eastern time.
            self.utc_offset_seconds = -4 * 3600
            self.dst_offset_seconds = 0

        # print("TZ Info:", self.utc_offset_seconds / 60 / 60, self.dst_offset_seconds)
