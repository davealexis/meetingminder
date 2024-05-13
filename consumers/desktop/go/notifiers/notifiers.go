package notifiers

import (
	"context"
	"log"
	"meetingminder/types"
	"time"
)

type Notifier interface {
	Init(ctx context.Context)
	Notify(eventTitle string, eventTime time.Time, notificationTier types.NotificationTier)
}

const (
	ThresholdUpcoming    = 300
	ThresholdAlmostThere = 60
	ThresholdStarting    = 10
	ThresholdStop        = 120
)

var notifiers = make(map[string]Notifier)

// ------------------------------------------------------------------------------------------------
func RegisterInstance(notifierType string, notifier Notifier) {
	notifiers[notifierType] = notifier
}

// ------------------------------------------------------------------------------------------------
func RegisterFromConfig(ctx context.Context, config *types.Config) {

	for _, notifierType := range config.Notifiers {
		switch notifierType {
		case "voice":
			// Not supported yet

		case "usb":
			notifier := &USBNotifier{}
			notifier.Init(ctx)
			RegisterInstance("usb", notifier)
		}
	}
}

// ------------------------------------------------------------------------------------------------
func Run(ctx context.Context, nextEventChannel chan types.Event) {
	go func() {
		for {
			select {
			case e := <-nextEventChannel:
				if e.Start.IsZero() {
					continue
				}

				for _, notifier := range notifiers {
					go notifier.Notify(e.Title, e.Start, e.Tier)
				}
			case <-ctx.Done():
				log.Println("Stopping notifiers")
				return
			}
		}
	}()
}
