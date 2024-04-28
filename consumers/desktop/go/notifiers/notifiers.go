package notifiers

import (
	"context"
	"meetingminder/types"
)

type Notifier interface {
	Run(ctx context.Context, nextEventChannel chan types.Event) chan bool
}

const (
	ThresholdUpcoming    = 300
	ThresholdAlmostThere = 60
	ThresholdStarting    = 10
	ThresholdStop        = 120
)

// ------------------------------------------------------------------------------------------------
func Start(ctx context.Context, notifierType string, nextEventChannel chan types.Event) error {

	var notifier Notifier

	switch notifierType {
	case "voice":
		return nil

	case "usb":
		notifier = USBNotifier{}

	default:
		return nil
	}

	readyChan := notifier.Run(ctx, nextEventChannel)
	ready := <-readyChan

	if !ready {
		return types.NotifierNotFound{}
	}

	return nil
}
