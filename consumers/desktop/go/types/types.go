package types

import "time"

// The Config struct holds the MongoDB connection information as well as
// a list of notifiers to use.
type Config struct {
	MongoUrl     string            `json:"mongoDataUrl"`
	MongoAPIKey  string            `json:"mongoDataApiKey"`
	MongoCluster string            `json:"mongoDataCluster"`
	Notifiers    []string          `json:"notifiers"`
	USBNotifiers map[string]string `json:"usbNotifiers"`
}

// The Event struct holds the basic information about an event.
// All we neeed is the title and the start time. This initial version of the
// application only really needs the start time. But it would be cool to
// Add an OLED or e-ink display so we can see the day's itinerary.
type Event struct {
	Title                 string    `json:"title"`
	Start                 time.Time `json:"startTime"`
	NotificationCountdown int
	Tier                  NotificationTier
}

type NotifierNotFound struct{}

func (e NotifierNotFound) Error() string {
	return "Notifier not found"
}

type NotificationTier string

const (
	Stop        NotificationTier = "Stop"
	Starting    NotificationTier = "Starting"
	AlmostThere NotificationTier = "Almost There"
	Pending     NotificationTier = "Pending"
	Waiting     NotificationTier = "Waiting"
)
