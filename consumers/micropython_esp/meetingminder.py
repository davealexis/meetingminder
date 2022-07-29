import urequests as requests
import uasyncio as asyncio
import ujson as json
import time
import secrets

# MicroPython's time module works on like Unix epoch time (Jan 1, 1970), except
# that it starts at Jan 1, 2000 instead. We need to adjust timestamps we receive
# from MongoDB to be compatible with the time module by deducting the MicroPython
# epoch from the incoming timestamps.
MPEpochOffset = 946702800

# This is the URL to the MongoDB Atlas Data API endpoint.
MongoUrl = 'https://data.mongodb-api.com/app/data-pvtrm/endpoint/data/beta/action/'


# .............................................................................
class MeetingMinder():

    # .........................................................................
    def __init__(self, ledFlasher):
        self.leds = ledFlasher
        self.events = []
        self.get_timezone_offset()

        self.Query = '''{
            "dataSource": "ClusterOne",
            "database": "notifications",
            "collection": "events",
            "pipeline": [
                {
                    "$addFields": {
                        "secondsUntil": {
                            "$dateDiff": {
                                "startDate": "$$NOW",
                                "endDate": {
                                    "$convert": {
                                        "input": "$startTime",
                                        "to": "date"
                                    }
                                },
                                "unit": "second"
                            }
                        },
                        "startTime": {
                            "$convert": {
                                "input": "$startTime",
                                "to": "date"
                            }
                        },
                        "timestamp": {
                            "$toLong": {
                                "$convert": {
                                    "input": "$startTime",
                                    "to": "date"
                                }
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "$expr": {
                            "$gt": [
                                "$secondsUntil",
                                0
                            ]
                        }
                    }
                },
                {
                    "$sort": {
                        "startTime": 1
                    }
                },
                {
                    "$limit": 5
                },
                {
                    "$project": {
                        "_id": 0,
                        "title": 1,
                        "startTime": 1,
                        "startTicks": {
                            "$toLong": "$startTime"
                        }
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
        return time.mktime(time.localtime()) + self.utc_offset_seconds
    
    # .........................................................................
    async def run(self):
        """
            Start background event fetcher and scheduler tasks.
        """

        asyncio.create_task(self.event_refresher_task())
        asyncio.create_task(self.event_scheduler_task())

    # .........................................................................
    async def event_refresher_task(self):
        """
            Periodically fetch the list of events from the MongoDB Atlas Data API.
            This method will be run as a background task, so needs to run
            forever, sleeping for a bit between fetches.
        """
        while True:
            events = await self.fetch_events()            
            events_in_progress = [e for e in self.events if e['status'] == 'notifying']
            
            if events_in_progress:
                in_progress = events_in_progress[0]
                events = events_in_progress + [e for e in events if e['time'] != in_progress['time']]
                
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
                asyncio.create_task(self.announce(next_event))

            await asyncio.sleep(10)

    # .........................................................................
    async def announce(self, event):
        """
            Wait for the configured time before the event starts, then start
            announcing the event.
            Exit when the event is done.
        """
        event_time = event["time"]
        # event_title = event["title"]   <-- You can use this to display the title of the event
        
        time_until_event = event_time - self.now

        while True:
            """
                We don't need to spin our wheels fast if the event is a relatively long
                time in the future. We can go to sleep for a long time, and wake up to
                check every now and then.
                When the meeting is 5 minutes out, we can start the announcement cycle.
            """
            
            # Make sure the event we're monitoring hasn't been cancelled or there is a
            # newer event.
            if event['time'] != self.events[0]['time']:
                break                
                            
            wait_time = await self.wait_time(event_time)

            if wait_time:
                await asyncio.sleep(wait_time)
                continue

            now = self.now
            time_until_event = event_time - now
            
            if time_until_event <= -60:
                await self.leds.off()
                self.events.pop(0)
                break
            elif time_until_event <= 10:          # 10 seconds before the event
                event['status'] = 'notifying'
                await self.leds.off()
                await self.leds.on(self.leds.Red)
            elif time_until_event <= 60:          # 1 minute before the event
                event['status'] = 'notifying'
                await self.leds.on(self.leds.Yellow)
            elif time_until_event <= 180:         # 3 minutes before the event
                await self.leds.on(self.leds.Green)
            elif time_until_event <= 300:         # 5 minutes before the event
                await self.leds.on(self.leds.Green)
                
            await asyncio.sleep(1)
    
    # .........................................................................
    async def wait_time(self, event_time):
        """
            Determine how long we can go to sleep for before we need to start
            actively managing the LEDs. e.g. If the meeting is hours away,
            we can sleep for an hour at a time until we get closer to the 
            time of the event.
        """

        time_till_event = event_time - self.now

        if time_till_event <= 300:       # 5 minutes
            if time_till_event > 3600:   # 1 hour
                # The meeting is more than an hour away. Sleep for an hour.
                sleepTime = 3600
            elif time_till_event > 600:  # 10 minutes
                # The meeting is less than an hour away, but more than 10 minutes.
                sleepTime = 600
            elif time_till_event > 360:  # 6 minutes
                sleepTime = 0
            else:
                sleepTime = 0

            return sleepTime

    # .........................................................................
    async def fetch_events(self):
        try:
            resp = requests.post(MongoUrl + "aggregate", data=self.Query, headers=self.QueryHeaders)
        except:
            # Failed. No biggie. We'll pull the events on the next go-around.
            return self.events

        event_list = []

        if resp.status_code == 200:
            if len(resp.text) > 0:
                doc = json.loads(resp.text)

                if doc.get("documents"):
                    events = doc["documents"]

                    if len(events):
                        for event in events:
                            event_list.append({
                                "title": event["title"],
                                "time": int(str(event["startTicks"])[0:-3]) - MPEpochOffset + self.dst_offset_seconds,
                                "status": "pending"
                            })
                elif doc.get("document"):
                    event = doc["document"]
                    event_list.append({
                        "title": event["title"],
                        "time": int(event["startTicks"][0:-3]) - MPEpochOffset + self.dst_offset_seconds,
                        "status": "pending"
                    })
        else:
            event_list = self.events
            
        timeNow = self.now
        
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
            self.utc_offset_seconds = (hours * 3600) + (minutes * 60 if hours > 0 else minutes * -60)
            
            # self.dst_offset_seconds *= -1
        except:
            # Failed to fetch the local timezone info. Default to Eastern time.
            self.utc_offset_seconds = -4 * 3600
            self.dst_offset_seconds = 0
