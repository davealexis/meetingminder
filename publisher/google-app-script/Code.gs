/*
    ------------------------------------------------------------------------------------------
    MeetingMinder Publisher
    ------------------------------------------------------------------------------------------

    This code integrates with a Google Calendar, and publises basic information about events to an
    intermediary database used by one or more MeetingMinder client devices or apps.
    
    Create a new file in this project called "secrets" (it will get the full name of "secrets.gs"), and
    add the following contents with the placeholders replaced with your actual values:

        const apiKey = "<your MongoDB Atlas API key for Data API>"

    The MongoDB Data API URLs below are the same for any account/project/database, since those
    identifiers are specified in the body of Data API requests.

    The "eventSource" constant identifies the calendar events for this particular calendar integration
    in the MongoDB data. This enables each calendar integration to manage its own data without affecting
    data for other calendars. It also enables extensions to the MeetingMinder clients that do things like
    display rich information about upcoming events.

    ------------------------------------------------------------------------------------------
*/

const mongoDataInsertApi = 'https://data.mongodb-api.com/app/data-pvtrm/endpoint/data/beta/action/insertMany'
const mongoDataDeleteApi = 'https://data.mongodb-api.com/app/data-pvtrm/endpoint/data/beta/action/deleteMany'
const eventSource = "Work Calendar"


// ------------------------------------------------------------------------------------------
function getMeetings() {
    // Delete existing data
    Logger.log("Deleting existing data...")
    deleteExistingEvents()

    // Get events for the next day
    var now = new Date()
    var to = new Date()
    to.setHours(to.getHours() + 24)
    var events = CalendarApp.getEvents(now, to)

    if (events.length == 0) {
        Logger.log("No events")
        return
    }

    // Insert new data
    Logger.log("Inserting new list of events...")

    var events = CalendarApp.getEvents(now, to)
    var eventList = []
    var eventCount = 0

    events.forEach(e => {
        eventCount++

        if (eventCount <= 5) {
            var id = e.getId()
            var eventTime = e.getStartTime()
            id = id.substring(0, id.indexOf("@"))

            eventList.push(
                {
                  "eventId": id,
                  "source": eventSource,
                  "title": e.getTitle(),
                  "startTime": e.getStartTime().toISOString()
                }
            ) 
        }
    })

    sendData(eventList)

    Logger.log("Done")
}

// ------------------------------------------------------------------------------------------
function sendData(data) {
    var request = {
        "method": "post",
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Request-Headers": "*",
            "api-key": mongoDbApiKey
        },
        "payload": JSON.stringify({
            "dataSource": "ClusterOne",
            "database": "notifications",
            "collection": "events",
            "documents": data
        })
    }

    response = UrlFetchApp.fetch(mongoDataInsertApi, request)
}

// ------------------------------------------------------------------------------------------
function deleteExistingEvents() {
    var request = {
        "method": "post",
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Request-Headers": "*",
            "api-key": mongoDbApiKey
        },
        "payload": JSON.stringify({
            "dataSource": "ClusterOne",
            "database": "notifications",
            "collection": "events",
            "filter": { "source": eventSource}
        })
    }

    response = UrlFetchApp.fetch(mongoDataDeleteApi, request)
}
