package main

// Build with go build -ldflags -H=windowsgui

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"meetingminder/notifiers"
	"meetingminder/types"
	"net/http"
	"os"
	"os/signal"
	"path"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/getlantern/systray"
)

//go:embed assets
var assets embed.FS

// We're using MongoDB Atlas, which enables simple interation using
// just standard REST APIs - no fancy, bloated client libraries.
// This is perfectly suited for IoT applications, where we're very concerned
// with efficiently running on resource-constrained environments.
//

// This represents the full MongoDB Data API query to fetch the event data.
// A "projection" step is used since we want to not have the ID fields
// in the response.
// The query itself is in the "pipeline" node. All of the nodes before "pipeline"
// are query metadata reuqired by the MongoDB API. They specify the Atlas
// cluster, database, and collection to query.
const QueryTemplate = `{
		"dataSource": "%s",
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
					"startTime": 1
				}
			}
		]
	}`

const (
	RefeshStartHour = 6
	RefeshEndHour   = 22
)

var config types.Config
var eventCache = []types.Event{}

// ------------------------------------------------------------------------------------------------
func main() {
	systray.Run(onReady, onExit)
}

// ------------------------------------------------------------------------------------------------
func onReady() {
	loadConfig()
	ctx, done := context.WithCancel(context.Background())
	ctx = context.WithValue(ctx, "config", config)
	wg := &sync.WaitGroup{}
	wg.Add(1)

	eventUpdate := make(chan types.Event, 5)

	systray.SetIcon(getIcon("assets/clock.ico"))
	activeMeeting := systray.AddMenuItem("No meeting", "No meeting")
	activeMeeting.SetIcon(getIcon("assets/sleep.ico"))
	systray.AddSeparator()
	mQuit := systray.AddMenuItem("Quit", "Quits this app")

	go func() {
		for {
			select {
			case event := <-eventUpdate:
				if event.Title == "" {
					event.Tier = types.Waiting
				}

				switch event.Tier {
				case types.Stop, types.Waiting:
					activeMeeting.SetTitle("No meeting")
					activeMeeting.SetIcon(getIcon("assets/sleep.ico"))
					systray.SetIcon(getIcon("assets/clock.ico"))
				case types.Starting:
					activeMeeting.SetTitle("Meeting: " + event.Title)
					activeMeeting.SetIcon(getIcon("assets/red.ico"))
					systray.SetIcon(getIcon("assets/red.ico"))
				case types.AlmostThere:
					activeMeeting.SetTitle("Meeting: " + event.Title)
					activeMeeting.SetIcon(getIcon("assets/yellow.ico"))
					systray.SetIcon(getIcon("assets/yellow.ico"))
				case types.Pending:
					activeMeeting.SetTitle("Meeting: " + event.Title)
					activeMeeting.SetIcon(getIcon("assets/green.ico"))
					systray.SetIcon(getIcon("assets/green.ico"))
				}
			case <-mQuit.ClickedCh:
				done()
				wg.Wait()
				systray.Quit()
				return
			}
		}
	}()

	// Now let's set some goroutine orchestration.
	// We're going to have
	// 	- one goroutine that watches for OS signals.
	// 	- one goroutine that polls the database for updated event data.
	// 	- one goroutine that schedules the LED shenanigans.
	// 	- one goroutine that handles the LED blinky-blinky.

	// Watch for OS signals - e.g. Ctrl-C, SIGTERM, etc.
	// When a signal is received, we'll tell the goroutines to stop.
	go watchForOsSignal(done)

	startNotifiers(ctx, eventUpdate)

	// Poll the database for updated event data.
	// Data about the next upcoming event is sent to the LED goroutine.
	go refreshEvents(ctx, wg)

	// Schedule the LED shenanigans.
	// This goroutine will manage when notifiers should be triggered.
	go scheduleEvents(ctx, eventUpdate)

	log.Println("Notification service started")
	log.Println("Press Ctrl+C to exit")
	wg.Wait()
	log.Println("Exiting")
}

// ------------------------------------------------------------------------------------------------
func onExit() {
	// Cleaning stuff here.
}

// ------------------------------------------------------------------------------------------------
func getIcon(s string) []byte {
	b, err := assets.ReadFile(s)
	if err != nil {
		fmt.Print(err)
	}
	return b
}

// ------------------------------------------------------------------------------------------------
func startNotifiers(ctx context.Context, nextEventChannel chan types.Event) {
	for _, n := range config.Notifiers {
		log.Printf("Starting notifier: %s", n)

		notifiers.Start(ctx, n, nextEventChannel)
	}
}

// ------------------------------------------------------------------------------------------------

// watchForOsSignal watches for OS signals and sends them to the done channel to tell
// other goroutines to stop.
func watchForOsSignal(done context.CancelFunc) {
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)

	sig := <-sigs
	log.Println("Got Crtl-C or SIGTERM")
	log.Println(sig)
	done()
}

// ------------------------------------------------------------------------------------------------

// loagConfig loads the configuration from the config.json file.
func loadConfig() {
	appPath, _ := os.Executable()
	configPath := path.Join(path.Dir(strings.Replace(appPath, "\\", "/", -1)), "meetingminder.config.json")

	file, err := os.ReadFile(configPath)
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
func refreshEvents(ctx context.Context, wg *sync.WaitGroup) {
	log.Println("Refresh events task started")
	ticker := time.NewTicker(2 * time.Minute)

	eventCache = fetchEvents()

	for e, event := range eventCache {
		eventCache[e].Start = event.Start.Local()
	}

	for {
		select {
		case <-ctx.Done():
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
				eventCache = fetchEvents()
			}
		}
	}
}

// ------------------------------------------------------------------------------------------------

// fetchEvents does the actual work of calling MongoDB to fetch the event data.
func fetchEvents() []types.Event {
	client := &http.Client{}
	query := fmt.Sprintf(QueryTemplate, config.MongoCluster)

	req, err := http.NewRequest("POST", config.MongoUrl+"/aggregate", strings.NewReader(query))
	if err != nil {
		log.Fatal(err)
	}

	req.Header.Add("Content-Type", "application/json")
	req.Header.Add("Access-Control-Request-Header", "*")
	req.Header.Add("api-key", config.MongoAPIKey)
	req.Header.Add("Connection", "close")

	resp, err := client.Do(req)
	if err != nil {
		log.Fatal(err)
	}

	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Fatal(err)
	}

	type MongoResponse struct {
		Documents []types.Event `json:"documents"`
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
func getNextEvent(events []types.Event) types.Event {
	var nextEvent types.Event

	for _, event := range events {
		if nextEvent.Start.IsZero() || event.Start.Before(nextEvent.Start) {
			if event.Start.After(time.Now()) {
				nextEvent = event
				nextEvent.Tier = types.Waiting
			}
		}
	}

	return nextEvent
}

// ------------------------------------------------------------------------------------------------

// scheduleEvents orchestrates the LED blinking once the time of the next event reaches within the
// 5-minute window. Once that happens, a message is sent to the goroutine that handles the LED
// blinking.
// It also listens for notifications from the database poller about the next upcoming event.
func scheduleEvents(ctx context.Context, notificationChannel chan types.Event) {
	ticker := time.NewTicker(1 * time.Second)

	var nextEvent types.Event

	for {
		select {
		case <-ticker.C:
			if nextEvent.Start.IsZero() && len(eventCache) > 0 {
				nextEvent = getNextEvent(eventCache)
			}

			if !nextEvent.Start.IsZero() {
				notificationStartThreshold := nextEvent.Start.Add((notifiers.ThresholdUpcoming*-1 - 5) * time.Second)

				if time.Now().After(notificationStartThreshold) {
					if !manageNotification(nextEvent, notificationChannel) {
						nextEvent = types.Event{}
					}
				}
			}
		case <-ctx.Done():
			log.Println("Stopping Notifier process")
			ticker.Stop()
			return
		}
	}
}

// ------------------------------------------------------------------------------------------------

// manageNotification manages blinking the LED for various intervals and colors depending on
// if the event start time is within 5 minutes, within 1 minute, and within 10 seconds.
func manageNotification(event types.Event, notificationChan chan types.Event) bool {
	if time.Now().After(event.Start.Add(-10 * time.Second)) {
		if time.Now().After(event.Start.Add(notifiers.ThresholdStop * time.Second)) {
			event.Tier = types.Stop
			notificationChan <- event

			return false
		}

		event.Tier = types.Starting
		notificationChan <- event

		return true
	}

	timeRemaining := time.Until(event.Start)

	if timeRemaining <= notifiers.ThresholdStarting*time.Second {
		event.Tier = types.Starting
	} else if timeRemaining <= notifiers.ThresholdAlmostThere*time.Second {
		event.Tier = types.AlmostThere
	} else if timeRemaining <= notifiers.ThresholdUpcoming*time.Second {
		event.Tier = types.Pending
	}

	notificationChan <- event

	return true
}
