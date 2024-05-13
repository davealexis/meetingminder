package notifiers

import (
	"context"
	"fmt"
	"log"
	"meetingminder/types"
	"time"

	"go.bug.st/serial"
	"go.bug.st/serial/enumerator"
)

type USBNotifier struct {
	Port             string
	Discovering      bool
	SupportedDevices map[string]string
	context          context.Context
	notifying        bool
}

// ------------------------------------------------------------------------------------------------
func (n *USBNotifier) Init(ctx context.Context) {
	config := ctx.Value("config").(*types.Config)
	n.SupportedDevices = config.USBNotifiers
	n.context = ctx

	go n.triggerDiscovery()
}

// ------------------------------------------------------------------------------------------------
func (n *USBNotifier) Notify(_ string, _ time.Time, notificationTier types.NotificationTier) {
	if n.Port == "" {
		if !n.Discovering {
			go n.triggerDiscovery()
		}

		return
	}

	if !n.notifying {
		n.notifying = true

		serialMode := serial.Mode{
			BaudRate: 9600,
			DataBits: 8,
			StopBits: 1,
			Parity:   serial.NoParity,
		}

		serial, err := serial.Open(n.Port, &serialMode)
		if err != nil {
			log.Println("USB notify error:", err, " Port:", n.Port, err)
			n.Port = ""
			return
		}

		defer serial.Close()

		switch notificationTier {
		case types.Stop, types.Waiting:
			_, err = serial.Write([]byte("off\r"))
		case types.Starting:
			_, err = serial.Write([]byte("red\r"))
		case types.AlmostThere:
			_, err = serial.Write([]byte("yellow\r"))
		case types.Pending:
			_, err = serial.Write([]byte("green\r"))
		}

		if err != nil {
			log.Println("USB notify error (2):", err, " Port:", n.Port)
			n.Port = ""
		}

		n.notifying = false
	}
}

// ------------------------------------------------------------------------------------------------
func (n *USBNotifier) triggerDiscovery() {
	n.Discovering = true
	deviceChan := n.discover()
	device := <-deviceChan

	n.Port = device
	n.Discovering = false
}

// ------------------------------------------------------------------------------------------------
// discover discovers and returns a channel of strings representing the names of serial devices that are
// supported by the application.
//
// The function continuously polls for available serial devices and checks if they are supported by the application.
// If a supported device is found, its name is sent to the channel and the function returns. If no supported devices
// are found after a certain period of time, a message is logged indicating that no devices were found.
//
// Returns:
// - deviceChan: a channel of string representing the COM port for the discovered serial device.
// ------------------------------------------------------------------------------------------------
func (n *USBNotifier) discover() chan string {
	deviceChan := make(chan string, 2)

	go func() {
		for {
			select {
			case <-n.context.Done():
				log.Println("Stopping USB notifier")
				return

			default:
			}

			ports, err := enumerator.GetDetailedPortsList()

			if err != nil {
				log.Fatal(err)
			}

			if len(ports) != 0 {
				// log.Println("Looking for MeetingMinder notifier...")

				for _, port := range ports {
					if port.IsUSB {
						fmt.Printf("   USB ID     %s:%s\n", port.VID, port.PID)
						fmt.Printf("   USB serial %s\n", port.SerialNumber)

						id := fmt.Sprintf("%s:%s", port.VID, port.PID)

						if name, ok := n.SupportedDevices[id]; ok {
							fmt.Printf("   %s\n", name)

							n.Port = port.Name
							deviceChan <- port.Name
							return
						}
					}
				}
			}

			// log.Println("No supported serial devices found")
			time.Sleep(2 * time.Second)
		}
	}()

	return deviceChan
}
