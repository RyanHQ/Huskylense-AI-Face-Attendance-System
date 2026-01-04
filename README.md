# AI Face Recognition Attendance System (HuskyLens + Arduino Mega + Raspberry Pi 4)

An offline/local-network AI face recognition attendance system using HuskyLens (Face Recognition mode) to detect face IDs, Arduino Mega to read HuskyLens via I2C, and a Raspberry Pi 4 to log attendance into SQLite and serve a Flask web dashboard.

Works fully offline inside LAN / hotspot (no cloud subscription).

---

## Features

- Multi-face recognition using HuskyLens trained IDs
- Automatic attendance logging (anti-spam: 1 record per minute per student)
- Register students (Face ID -> Name -> Class)
- Prevent duplicate names (case-insensitive)
- Edit / delete users
- Manage classes (add / delete class; safe delete only when no users assigned)
- Attendance table (filter by class)
- Analytics page
  - Per-class summary: Registered / Today / Total + Export by class
  - Student status (checked-in today or not)
- Export CSV
  - Export all records
  - Export by class (?class=ClassName)
- Reset actions with confirmation popups
  - Reset registered IDs
  - Reset attendance records
- Auto-start on boot (systemd service)

---

## System Overview

Data flow:

Student Face
  -> HuskyLens (Face Recognition) outputs Face ID
  -> Arduino Mega reads ID via I2C and prints "FACE:<ID>"
  -> Raspberry Pi reads USB Serial (/dev/ttyACM0)
  -> Logs to SQLite and serves Flask dashboard
  -> Browser opens http://<PI_IP>:5000

---

## Hardware Required

- HuskyLens V1.1 (Face Recognition mode)
- Arduino Mega 2560
- Raspberry Pi 4
- USB cable (Arduino -> Pi)
- Jumper wires (HuskyLens -> Mega)
- Power supplies

Optional:
- External monitor for Pi (dashboard display)
- Dedicated router/hotspot for stable LAN

---

## Wiring

### HuskyLens -> Arduino Mega (I2C)

HuskyLens SDA -> Mega SDA (Pin 20)
HuskyLens SCL -> Mega SCL (Pin 21)
HuskyLens VCC -> 5V
HuskyLens GND -> GND

On HuskyLens:
- Protocol = I2C
- Algorithm = Face Recognition

### Arduino Mega -> Raspberry Pi (USB Serial)

Arduino USB -> Raspberry Pi USB

Common device ports on Pi:
- /dev/ttyACM0 (most common)
- /dev/ttyUSB0 (if using USB-serial adapter)

---

## Repository Structure (Recommended)


## Repository Structure (Recommended)

```text
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

## HuskyLens Setup (Training Face IDs)

1) Set HuskyLens to Face Recognition mode
2) Enable Multiple Face Recognition (if available)
3) Use Learn to store faces (IDs become 1,2,3,...)
4) Set Protocol -> I2C

Tips:
- Keep face centered and lighting consistent
- If IDs become messy, clear learned data on HuskyLens and retrain

---

## Arduino Setup

1) Arduino IDE -> install DFRobot HuskyLens library
2) Upload: arduino/huskylens_attendance.ino

Expected serial output includes lines like:
FACE:6
FACE:2

The Raspberry Pi listens for "FACE:<ID>".

---

## Raspberry Pi Setup (Flask + Serial + SQLite)

### 1) Copy files to Pi

mkdir -p ~/attendance
cd ~/attendance
# Copy raspberry_pi/app.py and raspberry_pi/requirements.txt into this folder

### 2) Create venv + install dependencies

sudo apt update
sudo apt install -y python3-venv python3-pip

cd ~/attendance
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

### 3) Run manually (test)

python app.py

You should see:
- Serial connected message (if Arduino is plugged in)
- Flask running on 0.0.0.0:5000

### 4) Open dashboard from another device

Find Pi IP:
hostname -I

Open in browser (same Wi-Fi/hotspot):
http://<PI_IP>:5000

---

## Auto-start on Boot (systemd)

### 1) Create service file

sudo nano /etc/systemd/system/attendance.service

Paste and replace YOUR_USERNAME:

[Unit]
```text
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
```
[Install]
WantedBy=multi-user.target

### 2) Enable + start

sudo systemctl daemon-reload
sudo systemctl enable attendance.service
sudo systemctl restart attendance.service
sudo systemctl status attendance.service

### 3) View logs

sudo journalctl -u attendance.service -f

---

## Web Routes

Dashboard:
- /

Register:
- /register

Users:
- /users
- /edit_user/<id>
- /delete_user/<id>  (POST)

Classes:
- /classes

Attendance:
- /attendance
- /attendance?class=Class%20A

Analytics:
- /analytics

Export CSV:
- /export_csv
- /export_csv?class=Class%20A

Reset:
- /reset_ids        (POST)
- /reset_attendance (POST)

---

## Attendance Logging Rules

- Arduino prints: FACE:<ID>
- Raspberry Pi logs only if:
  - ID exists in users table
  - cooldown has passed for that ID (default 60 seconds)

Unknown IDs show in terminal:
Unknown ID: 6

---

## Configuration (Optional Environment Variables)

SERIAL_PORT=/dev/ttyACM0
BAUDRATE=115200
COOLDOWN=60
PORT=5000
HOST=0.0.0.0
ATTENDANCE_DB=attendance.db

---

## Troubleshooting

### Website not reachable from other devices
- Ensure devices are on the same network
- Confirm Pi IP (hostname -I)
- Confirm Flask binds to 0.0.0.0
- Allow port 5000 on firewall if enabled

### Serial device missing
ls /dev/ttyACM*
ls /dev/ttyUSB*
dmesg | grep -i tty

### Permission denied on serial
sudo usermod -aG dialout $USER
sudo reboot

### HuskyLens not detecting
- Mode = Face Recognition
- Protocol = I2C
- SDA/SCL wiring correct (Mega 20/21)

---

## Future Improvements

- Teacher/admin login
- Student photo thumbnails
- Better analytics charts
- Cloud sync/backup
- Kiosk mode for a dedicated display

---

## License

MIT License recommended.
