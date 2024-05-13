package notifiers

import (
	"context"
	"embed"
	"fmt"
	"meetingminder/types"
	"time"

	"github.com/getlantern/systray"
)

type SystrayNotifier struct {
	Assets        embed.FS
	activeMeeting *systray.MenuItem
}

// ------------------------------------------------------------------------------------------------
func (n *SystrayNotifier) Init(ctx context.Context) {
	systray.SetIcon(n.getIcon("assets/clock.ico"))
	n.activeMeeting = systray.AddMenuItem("No meeting", "No meeting")
	n.activeMeeting.SetIcon(n.getIcon("assets/sleep.ico"))
	systray.AddSeparator()
}

// ------------------------------------------------------------------------------------------------
func (n *SystrayNotifier) Notify(eventTitle string, eventTime time.Time, notificationTier types.NotificationTier) {
	if eventTitle == "" {
		notificationTier = types.Waiting
	}

	switch notificationTier {
	case types.Stop, types.Waiting:
		n.activeMeeting.SetTitle("No meeting")
		n.activeMeeting.SetIcon(n.getIcon("assets/sleep.ico"))
		systray.SetIcon(n.getIcon("assets/clock.ico"))
	case types.Starting:
		n.activeMeeting.SetTitle("Meeting: " + eventTitle)
		n.activeMeeting.SetIcon(n.getIcon("assets/red.ico"))
		systray.SetIcon(n.getIcon("assets/red.ico"))
	case types.AlmostThere:
		n.activeMeeting.SetTitle("Meeting: " + eventTitle)
		n.activeMeeting.SetIcon(n.getIcon("assets/yellow.ico"))
		systray.SetIcon(n.getIcon("assets/yellow.ico"))
	case types.Pending:
		n.activeMeeting.SetTitle("Meeting: " + eventTitle)
		n.activeMeeting.SetIcon(n.getIcon("assets/green.ico"))
		systray.SetIcon(n.getIcon("assets/green.ico"))
	}
}

// ------------------------------------------------------------------------------------------------
func (n SystrayNotifier) getIcon(s string) []byte {
	b, err := n.Assets.ReadFile(s)

	if err != nil {
		fmt.Print(err)
	}

	return b
}
