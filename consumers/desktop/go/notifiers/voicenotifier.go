package notifiers

// *** TODO ***
// Implement voice notifier

import (
	"log"
	"meetingminder/types"
	"time"

	"github.com/go-ole/go-ole"
	"github.com/go-ole/go-ole/oleutil"
)

type VoiceNotifier struct {
}

// ------------------------------------------------------------------------------------------------
func (n VoiceNotifier) Run(nextEventChannel chan types.Event, done chan bool) chan bool {
	return nil
}

// ------------------------------------------------------------------------------------------------
func (n VoiceNotifier) notify(eventTitle string, eventTime time.Time, notificationTier types.NotificationTier) error {
	say(eventTitle, 0)

	return nil
}

// ------------------------------------------------------------------------------------------------
func say(text string, rate int) {
	ole.CoInitialize(0)
	defer ole.CoUninitialize()

	unknown, err := oleutil.CreateObject("SAPI.SpVoice")
	if err != nil {
		log.Fatal(err)
	}

	sapi, err := unknown.QueryInterface(ole.IID_IDispatch)
	defer sapi.Release()
	if err != nil {
		log.Fatal(err)
	}

	_, err = oleutil.PutProperty(sapi, "Rate", rate)
	if err != nil {
		log.Fatal(err)
	}

	_, err = oleutil.CallMethod(sapi, "Speak", text)
	if err != nil {
		log.Fatal(err)
	}
}
