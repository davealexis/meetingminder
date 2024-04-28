#define RED_PIN 18
#define BLUE_PIN 9
#define GREEN_PIN 17

int32_t lastUpdate = 0;

void setup() {
    Serial.begin(9600);
    
    pinMode(RED_PIN, OUTPUT);
    pinMode(BLUE_PIN, OUTPUT);
    pinMode(GREEN_PIN, OUTPUT);

    digitalWrite(RED_PIN, HIGH);
    digitalWrite(BLUE_PIN, HIGH);
    digitalWrite(GREEN_PIN, HIGH);
}

void loop() {
    if (Serial.available()) {
        String command = Serial.readStringUntil('\r');
        lastUpdate = millis();
        
        if (command.equals("red")) {
                // set color to red
                digitalWrite(RED_PIN, LOW);
                digitalWrite(BLUE_PIN, HIGH);
                digitalWrite(GREEN_PIN, HIGH);
        } else if (command.equals("green")) {
                // turn off
                digitalWrite(RED_PIN, HIGH);
                digitalWrite(BLUE_PIN, HIGH);
                digitalWrite(GREEN_PIN, LOW);
        } else if (command.equals("blue")) {
                // turn off
                digitalWrite(RED_PIN, HIGH);
                digitalWrite(BLUE_PIN, LOW);
                digitalWrite(GREEN_PIN, HIGH);
        } else if (command.equals("yellow")) {
                // turn off
                digitalWrite(RED_PIN, LOW);
                digitalWrite(BLUE_PIN, HIGH);
                digitalWrite(GREEN_PIN, LOW);
        } else if (command.equals("off")) {
                // turn off
               digitalWrite(RED_PIN, HIGH);
               digitalWrite(BLUE_PIN, HIGH);
               digitalWrite(GREEN_PIN, HIGH);
        }
    }

    delay(100);

    int32_t now = millis();

    // Turn off the LED if it's been over 1 minute since the last update.
    // This is to prevent a broken connection causing the light to be on indefinately.
    if (lastUpdate > 0 && now - lastUpdate > 1000 * 60) {
        digitalWrite(RED_PIN, HIGH);
        digitalWrite(BLUE_PIN, HIGH);
        digitalWrite(GREEN_PIN, HIGH);
        lastUpdate = 0;
    }
}
