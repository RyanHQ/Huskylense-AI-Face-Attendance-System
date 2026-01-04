# Arduino (HuskyLens -> Raspberry Pi Serial Bridge)

This Arduino Mega sketch reads **HuskyLens V1.1** face recognition results via **I2C** and forwards only the detected **Face ID** to the Raspberry Pi using **USB Serial**.

The Raspberry Pi Flask server listens for this line format:

- `FACE:<ID>`

Example:
- `FACE:2`

---

## Why Arduino Mega is needed

HuskyLens V1.1 has practical compatibility limitations for direct integration with Raspberry Pi 4 (I2C/UART handling depends on firmware/protocol support and is not always reliable/straightforward).  
So the Arduino Mega acts as a stable bridge:

HuskyLens (I2C) -> Arduino Mega -> Raspberry Pi (USB Serial)

---

## Wiring (I2C)

HuskyLens -> Arduino Mega 2560

- SDA -> SDA (Pin 20)
- SCL -> SCL (Pin 21)
- VCC -> 5V
- GND -> GND

---

## HuskyLens Settings (on device)

- Algorithm: **Face Recognition**
- Protocol: **I2C**
- Train multiple faces (IDs 1,2,3,...)

---

## Upload Steps

1. Open Arduino IDE
2. Install HuskyLens library:
   - DFRobot HuskyLens (Library Manager)
3. Open the sketch:
   - `huskylens_attendance.ino`
4. Select board:
   - **Arduino Mega 2560**
5. Select correct COM port
6. Upload

---

## Serial Output

Arduino prints:
- Debug lines (optional): `ID=... X=... Y=...`
- Attendance trigger line: `FACE:<ID>`

If you want only `FACE:<ID>` lines, set `ONLY_FACE_LINES = true;` in the sketch.

---

## Testing

Open Serial Monitor at:
- **115200 baud**

Show your face to HuskyLens. If recognized, you should see:
- `FACE:<ID>`

If HuskyLens returns ID 0 for unknown, the sketch can ignore it (optional setting).

---

## Troubleshooting

### "HuskyLens init failed"
- Check wiring SDA/SCL (Mega uses pins 20/21)
- Confirm HuskyLens protocol is set to **I2C**
- Confirm HuskyLens is powered (5V + GND)

### No FACE lines on Serial Monitor
- Ensure HuskyLens is in **Face Recognition** mode
- Ensure you trained faces (Learn)
- Increase lighting / face distance consistency

---
