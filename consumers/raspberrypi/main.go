package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/stianeikeland/go-rpio/v4"
)

// The Event struct holds the basic information about an event.
// All we neeed is the title and the start time. This initial version of the
// application only really needs the start time. But it would be cool to
// Add an OLED or e-ink display so we can see the day's itinerary.
type Event struct {
	Title string    `json:"title"`
	Start time.Time `json:"startTime"`
}

// The Config struct holds the MongoDB connection information.
// We're using MongoDB Atlas, which enables simple interation using
// just standard REST APIs - no fancy, bloated client libraries.
// This is perfectly zuited for IoT applications, where we're very concerned
// with efficiently running on resource-constrained environments.
type Config struct {
	MongoUrl     string `json:"mongoDataUrl"`
	MongoAPIKey  string `json:"mongoDataApiKey"`
	MongoCluster string `json:"mongoDataCluster"`
}

// This represents the full MongoDB Data API query to fetch the event data.
// A "projection" step is used since we want to not have the ID fields
// in the response.
// The query itself is in the "filter" node. All of the nodes before "filter"
// are query metadata reuqired by the MongoDB API. They specify the Atlas
// cluster, database, and collection to query.
const QueryTemplate = `{
	"dataSource": "%s",
	"database": "notifications",
	"collection": "events",
	"filter": {},
	"projection": {
		"_id": 0,
		"title": 1,
		"startTime": 1
	}
}`

const (
	RefeshStartHour = 6
	RefeshEndHour   = 22
)

var config Config

// Here, we define the LED pins for the RGB LED.
var (
	redLed   = rpio.Pin(2)
	greenLed = rpio.Pin(3)
	blueLed  = rpio.Pin(4)
)

// ------------------------------------------------------------------------------------------------
func main() {
	loadConfig()

	// Initialize the GPIO library
	if err := rpio.Open(); err != nil {
		log.Println(err)
		os.Exit(1)
	}
	defer rpio.Close()

	// Set up LED pins as outputs
	redLed.Output()
	greenLed.Output()
	blueLed.Output()

	// The GPIO pins on the Raspberry Pi seem to be pulled high by default.
	// This means that turning the LEDs on is counter-intuitively done by
	// setting the pins low (or off).
	// These 3 lines are ensuring that the LEDs are off by setting them high.
	redLed.High()
	greenLed.High()
	blueLed.High()

	// Now let's set some goroutine orchestration.
	// We're going to have
	// 	- one goroutine that watches for OS signals.
	// 	- one goroutine that polls the database for updated event data.
	// 	- one goroutine that schedules the LED shenanigans.
	// 	- one goroutine that handles the LED blinky-blinky.
	done := make(chan bool)
	wg := &sync.WaitGroup{}
	wg.Add(1)
	eventUpdate := make(chan Event, 1)

	// Watch for OS signals - e.g. Ctrl-C, SIGTERM, etc.
	// When a signal is received, we'll tell the goroutines to stop.
	go watchForOsSignal(done)

	// Poll the database for updated event data.
	// Data about the next upcoming event is sent to the LED goroutine.
	go refreshEvents(done, eventUpdate, wg)

	// Schedule the LED shenanigans.
	// This goroutine will turn the LEDs on and off based on the next upcoming event.
	go notify(eventUpdate, done)

	log.Println("Notification service started")
	log.Println("Press Ctrl+C to exit")
	wg.Wait()
	log.Println("Exiting")
}

// ------------------------------------------------------------------------------------------------

// watchForOsSignal watches for OS signals and sends them to the done channel to tell
// other goroutines to stop.
func watchForOsSignal(done chan bool) {
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)

	sig := <-sigs
	log.Println()
	log.Println(sig)
	done <- true
}

// ------------------------------------------------------------------------------------------------

// loagConfig loads the configuration from the config.json file.
func loadConfig() {
	file, err := ioutil.ReadFile("config.json")
	if err != nil {
		log.Fatal(err)
	}

	err = json.Unmarshal(file, &config)
	if err != nil {
		log.Fatal(err)
	}
}

// ------------------------------------------------------------------------------------------------

// refreshEvents polls the database for updated event data.
// Once the list of events is retrieved, they are scanned to determine which is the next upcoming
// event. It will typically be the first event in the list, but the list may contain older events
// that happened since the last time the MongoDB collection was updated.
func refreshEvents(done chan bool, eventUpdate chan Event, wg *sync.WaitGroup) {
	ticker := time.NewTicker(1 * time.Minute)

	events := fetchEvents()
	nextEvent := getNextEvent(events)
	eventUpdate <- nextEvent

	for {
		select {
		case <-done:
			log.Println("Stopping event refresh process")
			ticker.Stop()
			wg.Done()
			return
		case <-ticker.C:
			// Refresh events only during "work" hours plus a reasonable window (6am - 10pm).
			// This is to avvoid calling the MongoDB API too often during perios when the
			// calendar is not likely to change, while still making sure we don't miss the
			// first event of the next day.
			if time.Now().Hour() > RefeshStartHour && time.Now().Hour() < RefeshEndHour {
				events := fetchEvents()
				nextEvent := getNextEvent(events)
				eventUpdate <- nextEvent
			}
		}
	}
}

// ------------------------------------------------------------------------------------------------

// fetchEvents does the actual work of calling MongoDB to fetch the event data.
func fetchEvents() []Event {
	client := &http.Client{}
	query := fmt.Sprintf(QueryTemplate, config.MongoCluster)

	req, err := http.NewRequest("POST", config.MongoUrl+"/find", strings.NewReader(query))
	if err != nil {
		log.Fatal(err)
	}

	req.Header.Add("Content-Type", "application/json")
	req.Header.Add("Access-Control-Request-Header", "*")
	req.Header.Add("api-key", config.MongoAPIKey)

	resp, err := client.Do(req)
	if err != nil {
		log.Fatal(err)
	}

	defer resp.Body.Close()

	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		log.Fatal(err)
	}

	type MongoResponse struct {
		Documents []Event `json:"documents"`
	}

	var response MongoResponse
	err = json.Unmarshal(bodyBytes, &response)
	if err != nil {
		log.Fatal(err)
	}

	return response.Documents
}

// ------------------------------------------------------------------------------------------------

// getNextEvent scans the list of events and returns the next upcoming event.
func getNextEvent(events []Event) Event {
	var nextEvent Event

	for _, event := range events {
		if nextEvent.Start.IsZero() || event.Start.Before(nextEvent.Start) {
			if event.Start.After(time.Now()) {
				nextEvent = event
			}
		}
	}

	return nextEvent
}

// ------------------------------------------------------------------------------------------------

// notify orchestrates the LED blinking once the time of the next event reaches within the
// 5-minute window. Once that happens, a message is sent to the goroutine that handles the LED
// blinking.
// It also listens for notifications from the database poller about the next upcoming event.
func notify(nextEventChannel chan Event, done chan bool) {
	// Listen for updates to next event channel
	// Set up ticker to wait for next event
	log.Println("Notifier started")
	ticker := time.NewTicker(5 * time.Second)

	var (
		nextEvent Event
	)

	for {
		select {
		case <-ticker.C:
			if !nextEvent.Start.IsZero() {
				if time.Now().After(nextEvent.Start.Add(5 * time.Minute)) {
					log.Println("Clearing next event")
					nextEvent = Event{}
				} else {
					showNotification(nextEvent)
				}
			}
		case e := <-nextEventChannel:
			nextEvent = e
			// log.Printf("Event Update: %s (%s)\n", nextEvent.Title, nextEvent.Start.Local().Format(time.RFC822))
		case <-done:
			log.Println("Stopping Notifier process")
			ticker.Stop()
			return
		}
	}

}

// ------------------------------------------------------------------------------------------------

// showNotification manages blinking the LED for various intervals and colors depending on
// if the event start time is within 5 minutes, within 1 minute, and within 10 seconds.
func showNotification(event Event) {
	if time.Now().After(event.Start.Add(-10 * time.Second)) {
		log.Println("Event '", event.Title, "'is starting")
		redLed.Low()
		time.Sleep(5 * time.Second)
		redLed.High()
	} else {
		timeRemaining := time.Until(event.Start)

		if timeRemaining < 1*time.Minute {
			log.Println(int(timeRemaining.Seconds()), "seconds until event")

			for i := 0; i < 10; i++ {
				greenLed.Low()
				redLed.Low()
				time.Sleep(150 * time.Millisecond)
				greenLed.High()
				redLed.High()
				time.Sleep(150 * time.Millisecond)
			}
		} else if timeRemaining < 5*time.Minute {
			log.Println(int(timeRemaining.Minutes()), "minutes until event")

			for i := 0; i < 2; i++ {
				greenLed.Low()
				time.Sleep(500 * time.Millisecond)
				greenLed.High()
				time.Sleep(500 * time.Millisecond)
			}
		}
	}
}
