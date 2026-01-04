# Huskylense-AI-Face-Attendance-System
Huskylense-AI-Face-Attendance-System-with-ArduinoMega-and-RaspberryPI4

```md
# AI Face Recognition Attendance System (HuskyLens + Arduino Mega + Raspberry Pi 4)

An offline/local-network **AI face recognition attendance system** using **HuskyLens (Face Recognition mode)** to detect face IDs, **Arduino Mega** to read HuskyLens data via **I2C**, and a **Raspberry Pi 4** to log attendance into **SQLite** and serve a **Flask web dashboard**.

> ✅ Works fully offline inside LAN / hotspot (no cloud subscription)

---

## Features

- **Multi-face recognition** using HuskyLens trained IDs
- **Automatic attendance logging** (anti-spam: **1 record per minute per student**)
- **Register students** (Face ID → Name → Class)
- **Prevent duplicate names** (case-insensitive)
- **Edit / delete users**
- **Manage classes** (add / delete class; safe delete only when no users assigned)
- **Attendance table** (filter by class)
- **Analytics page**
  - Per-class summary: Registered / Today / Total + Export by class
  - Student status (checked-in today or not)
- **Export CSV**
  - Export all records
  - Export by class (`?class=ClassName`)
- **Reset actions** with confirmation popups
  - Reset registered IDs
  - Reset attendance records
- **Auto-start on boot** (systemd service)

---

## System Overview

**Data Flow**

```

Student Face
↓
HuskyLens (Face Recognition)  → outputs Face ID
↓ I2C (SDA/SCL)
Arduino Mega 2560             → prints FACE:<ID> to Serial
↓ USB Serial (/dev/ttyACM0)
Raspberry Pi 4 (Python Flask) → logs to SQLite → serves web dashboard
↓
Browser (phone/laptop)        → http://<PI_IP>:5000

```

---

## Hardware Required

- **HuskyLens V1.1** (Face Recognition mode)
- **Arduino Mega 2560**
- **Raspberry Pi 4**
- USB cable (Arduino → Pi)
- Jumper wires (HuskyLens → Mega)
- Power supplies

Optional:
- External monitor for Pi (dashboard display)
- Dedicated router/hotspot for stable LAN

---

## Wiring

### HuskyLens → Arduino Mega (I2C)

| HuskyLens | Arduino Mega |
|----------|--------------|
| SDA      | SDA (Pin 20) |
| SCL      | SCL (Pin 21) |
| VCC      | 5V           |
| GND      | GND          |

✅ On HuskyLens: set **Protocol = I2C** and **Algorithm = Face Recognition**.

### Arduino Mega → Raspberry Pi (USB Serial)

- Arduino USB → Raspberry Pi USB
- On Pi, the port is usually:
  - `/dev/ttyACM0` (common)
  - or `/dev/ttyUSB0`

---

## Repository Structure (Recommended)

```

AI-Face-Attendance-System/
├─ README.md
├─ LICENSE
├─ .gitignore
├─ arduino/
│  ├─ huskylens_attendance.ino
│  └─ README_arduino.md
├─ raspberry_pi/
│  ├─ app.py
│  ├─ requirements.txt
│  └─ schema.sql
└─ deployment/
├─ attendance.service
└─ install.sh

```

---

## Setup HuskyLens (Training Face IDs)

1. Power HuskyLens and enter **Face Recognition** mode
2. Enable **Multiple Face Recognition** (if available)
3. Press **Learn** to store faces for multiple people
4. HuskyLens will assign IDs: 1,2,3,...
5. Set **Protocol → I2C**

Tip:
- Make sure the face is centered and lighting is good
- If IDs get messy, you can reset/clear HuskyLens learned data from device settings

---

## Upload Arduino Code

1. Open Arduino IDE
2. Install HuskyLens library (DFRobot HuskyLens)
3. Upload:
   - `arduino/huskylens_attendance.ino`

Serial output will include lines like:
```

FACE:6
FACE:2

````
The Raspberry Pi reads these `FACE:<ID>` lines.

---

## Raspberry Pi Setup (Flask + Serial + SQLite)

### 1) Copy files to Pi
On the Pi:
```bash
mkdir -p ~/attendance
cd ~/attendance
# Copy raspberry_pi/app.py and requirements.txt here
````

### 2) Create virtual environment + install dependencies

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip

cd ~/attendance
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3) Run the server manually (test)

```bash
python app.py
```

Output should look like:

```
[OK] Serial connected: /dev/ttyACM0 @ 115200
 * Running on http://0.0.0.0:5000
```

### 4) Open from another device

Find Pi IP:

```bash
hostname -I
```

On phone/laptop (same Wi-Fi/hotspot):

```
http://<PI_IP>:5000
```

---

## Auto-start on Boot (systemd)

### 1) Create service file

```bash
sudo nano /etc/systemd/system/attendance.service
```

Paste this (replace `YOUR_USERNAME`):

```ini
[Unit]
Description=AI Attendance Flask Server (HuskyLens)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/attendance
Environment="PATH=/home/YOUR_USERNAME/attendance/venv/bin"
ExecStart=/home/YOUR_USERNAME/attendance/venv/bin/python /home/YOUR_USERNAME/attendance/app.py
Restart=always
RestartSec=3
# SupplementaryGroups=dialout

[Install]
WantedBy=multi-user.target
```

### 2) Enable + start

```bash
sudo systemctl daemon-reload
sudo systemctl enable attendance.service
sudo systemctl restart attendance.service
sudo systemctl status attendance.service
```

### 3) View logs

```bash
sudo journalctl -u attendance.service -f
```

---

## Web Dashboard Pages

* `/` **Dashboard**
* `/register` Register student (Face ID → Name → Class)
* `/users` View users + edit/delete
* `/classes` Add/delete classes
* `/attendance` View attendance records (filter by class)
* `/analytics` Per-class summary + student status (today)
* `/export_csv` Export all attendance
* `/export_csv?class=Class%20A` Export by class

Reset actions (POST):

* `/reset_ids`
* `/reset_attendance`

---

## Serial / Attendance Rules

* Arduino prints: `FACE:<ID>`
* Raspberry Pi reads serial and logs attendance only if:

  * ID exists in `users` table
  * Last logged time for that ID is older than **COOLDOWN_SECONDS** (default 60s)
* Unknown IDs will show in terminal:

  * `Unknown ID: 6`

---

## Configuration (Optional Environment Variables)

You can override defaults:

```bash
export SERIAL_PORT=/dev/ttyACM0
export BAUDRATE=115200
export COOLDOWN=60
export PORT=5000
export HOST=0.0.0.0
export ATTENDANCE_DB=attendance.db
```

---

## Troubleshooting

### 1) Website not accessible from phone/laptop

* Make sure your phone/laptop is on the **same network** as the Pi
* Check Pi IP again (`hostname -I`)
* Ensure Flask binds to **0.0.0.0**
* If firewall exists, allow port **5000**

### 2) Serial not found (/dev/ttyACM0 missing)

Check:

```bash
ls /dev/ttyACM*
ls /dev/ttyUSB*
dmesg | grep -i tty
```

### 3) Permission denied on serial

Add user to dialout:

```bash
sudo usermod -aG dialout $USER
sudo reboot
```

### 4) HuskyLens not detecting

* Ensure HuskyLens mode is **Face Recognition**
* Protocol = **I2C**
* Check wiring SDA/SCL pins on Mega (20/21)

---

## Future Improvements

* Teacher/admin login
* Photo thumbnails for registered students
* Better analytics charts (graphs)
* Cloud sync / backup
* Multi-device kiosk display mode

---

## License

MIT License (recommended).

```
```
