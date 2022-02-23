const mongoDataInsertApi = 'https://data.mongodb-api.com/app/data-pvtrm/endpoint/data/beta/action/insertMany'
const mongoDataDeleteApi = 'https://data.mongodb-api.com/app/data-pvtrm/endpoint/data/beta/action/deleteMany'

const mongoApiKey = "<your-api-key>"        // <-- Replace with your api key
const eventSource = "<Calendar Name>"       // <-- Replace with your calendar name


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
            "api-key": apiKey
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
            "api-key": apiKey
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