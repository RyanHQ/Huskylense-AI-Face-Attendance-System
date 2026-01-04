/*
  HuskyLens Face Recognition Attendance (Arduino Mega)
  - HuskyLens connected to Arduino Mega via I2C
    SDA = 20, SCL = 21, VCC = 5V, GND = GND
  - HuskyLens should be set to Face Recognition mode + I2C protocol
  - Arduino prints FACE:<ID> when a recognized face is detected
  - Also prints debug info (ID, X, Y, W, H)

  Serial output examples:
    HuskyLens ready!
    ID=2  X=114  Y=34  W=48  H=65
    FACE:2
*/

#include "HUSKYLENS.h"
#include "Wire.h"

HUSKYLENS huskylens;

// Optional: Set to true if you want only FACE:<ID> lines (less noise)
bool ONLY_FACE_LINES = false;

// Optional: If HuskyLens outputs ID=0 when unknown, ignore it
bool IGNORE_ID_0 = true;

// Small helper to print one result
void printResult(const HUSKYLENSResult &r) {
  if (!ONLY_FACE_LINES) {
    Serial.print("ID=");
    Serial.print(r.ID);
    Serial.print("  X=");
    Serial.print(r.xCenter);
    Serial.print("  Y=");
    Serial.print(r.yCenter);
    Serial.print("  W=");
    Serial.print(r.width);
    Serial.print("  H=");
    Serial.println(r.height);
  }

  // Print the attendance trigger line that Raspberry Pi reads
  Serial.print("FACE:");
  Serial.println(r.ID);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();  // Mega: SDA=20, SCL=21

  // Keep trying until HuskyLens responds
  while (!huskylens.begin(Wire)) {
    Serial.println("HuskyLens init failed (check I2C wiring + HuskyLens protocol set to I2C)");
    delay(500);
  }

  Serial.println("HuskyLens ready!");
}

void loop() {
  // Request latest recognition results
  if (!huskylens.request()) {
    if (!ONLY_FACE_LINES) Serial.println("Request failed");
    delay(100);
    return;
  }

  // Read all results available in this frame
  while (huskylens.available()) {
    HUSKYLENSResult result = huskylens.read();

    // In some firmware/modes: ID=0 can mean unknown/unlearned
    if (IGNORE_ID_0 && result.ID == 0) {
      if (!ONLY_FACE_LINES) {
        Serial.print("ID=0 (ignored)  X=");
        Serial.print(result.xCenter);
        Serial.print("  Y=");
        Serial.print(result.yCenter);
        Serial.print("  W=");
        Serial.print(result.width);
        Serial.print("  H=");
        Serial.println(result.height);
      }
      continue;
    }

    // Trigger for Pi logging
    printResult(result);
  }

  delay(100);
}
