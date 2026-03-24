# JR Train Disruption LINE Notification Monitoring System

[日本語版はこちら](README_ja.md)

This system periodically monitors JR (East Japan / West Japan) train disruptions, delays, and cancellations via Yahoo! Transit Info, and sends instant push notifications through the LINE Messaging API when an anomaly (disruption, cancellation, etc.) is detected.
The instructions below use Raspberry Pi 5 as a deployment example.
Note: You must create a LINE Official Account before you can access the LINE Developers Console.

<br>
<img src=doc/images/sample1.jpg width="300">

---

## Project Structure

```
jr-monitor/
├── config.py              # Configuration (tokens, line names, interval)
├── monitor.py             # Main loop
├── line_client.py         # LINE Messaging API wrapper
├── scraper.py             # Yahoo! Transit Info scraper
├── state.py               # State management (JSON persistence)
├── requirements.txt       # Dependencies
├── jr-monitor.service     # systemd unit file
├── .env.example           # Environment variable template
└── tests/
    ├── test_scraper.py
    ├── test_line.py
    └── test_state.py
```

---

## Setup

### 1. LINE Developers Configuration

0. Create a LINE Official Account
1. Log in to [LINE Developers Console](https://developers.line.biz/)
2. Create a Provider → Create a "Messaging API" channel
3. Issue a **Channel Access Token** (long-lived token) and save it
4. Add your LINE Official Account as a friend in your LINE app
5. Find your **Your User ID** in the channel's "Webhook settings" (a string starting with `U`)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and fill in your token and user ID
```

**For local execution:**
```bash
export LINE_CHANNEL_TOKEN="your_token"
export LINE_USER_ID="U..."
# or
source .env   # use python-dotenv for dotenv-format files
```

### 4. Configure Target Train Lines

Edit `TARGET_LINES` in `config.py` to set the train lines you want to monitor.
Line names must exactly match the names shown on Yahoo! Transit Info (no `JR` prefix required). Comment out lines you don't need.

```python
TARGET_LINES: list[str] = [
#    "山手線",
#    "中央線(快速)[東京～高尾]",
#    "京浜東北根岸線",
    "東海道本線[東京～熱海]",
    "横須賀線",
    "湘南新宿ライン",
#    "埼京川越線[羽沢横浜国大～川越]",
#    "上野東京ライン",
#    "常磐線(快速)[品川～取手]",
#    "総武線(快速)[東京～千葉]",
]
```

### 5. Configure Monitoring Hours

Edit `MONITORING_WINDOWS` in `config.py` to specify the time windows during which notifications are sent.
List one or more `(start_time, end_time)` tuples in `"HH:MM"` format.
Outside of the specified windows, neither scraping nor notifications will occur.

```python
MONITORING_WINDOWS: list[tuple[str, str]] = [
    ("05:30", "08:30"),   # Morning commute hours
    ("14:30", "20:30"),   # Evening / night commute hours
]
```

### 6. Configure Check Interval

Set the check interval in seconds via `CHECK_INTERVAL` in `config.py` (default: 60 seconds).

```python
CHECK_INTERVAL: int = 60  # Fetch train status every 60 seconds
```

---

## Running Tests

```bash
pytest tests/ -v
```

With coverage report:

```bash
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## Dry Run (Smoke Test)

You can verify the system works without actually sending LINE messages by using dry-run mode:

```bash
python monitor.py --dry-run
```

After successful startup, check logs are printed at the interval set by `CHECK_INTERVAL` (default: 60 seconds).
Press `Ctrl+C` to stop.

---

## Production Run

```bash
python monitor.py
```

---

## Deploying to Raspberry Pi

### Prerequisites

- Raspberry Pi OS (Bullseye or later) / Python 3.10+
- Internet connection
- systemd available

### Steps

#### 1. Copy Files to Raspberry Pi

```bash
# Run on Raspberry Pi
sudo mkdir -p /opt/jr-monitor /var/lib/jr-monitor
sudo chown pi:pi /opt/jr-monitor /var/lib/jr-monitor

# Copy files from local machine (e.g., via scp / rsync)
rsync -av jr-monitor/ pi@raspberrypi.local:/opt/jr-monitor/
```

#### 2. Create Python Virtual Environment and Install Dependencies

```bash
cd /opt/jr-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Create Environment Variable File

```bash
sudo nano /etc/jr-monitor.env
```

Contents:
```
LINE_CHANNEL_TOKEN=your_channel_access_token
LINE_USER_ID=Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```bash
sudo chmod 600 /etc/jr-monitor.env
```

#### 4. Create Log Directory

```bash
sudo mkdir -p /var/log
# You can also change LOG_FILE in config.py to a path like /home/pi/jr-monitor.log
```

#### 5. Install systemd Service

```bash
sudo cp /opt/jr-monitor/jr-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jr-monitor
sudo systemctl start jr-monitor
```

#### 6. Verify Operation

```bash
# Check status
sudo systemctl status jr-monitor

# Follow logs in real time
sudo journalctl -u jr-monitor -f

# Stop service
sudo systemctl stop jr-monitor

# Disable service
sudo systemctl disable jr-monitor
```

#### 7. Configure Auto-Restart (Optional)

Verify the following is included in the `[Service]` section of `jr-monitor.service`:

```ini
Restart=on-failure
RestartSec=30s
```

This causes the service to automatically restart 30 seconds after a crash.

---

## Checking Logs

```bash
# systemd journal
sudo journalctl -u jr-monitor -n 100

# Read log file directly
tail -f /var/log/jr-monitor.log
```

---

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| No LINE message received | Incorrect token or user ID | Verify with `--dry-run`, then check the LINE API dashboard |
| Disruptions not detected | Train line name mismatch | Compare actual display names on Yahoo! Transit Info with `TARGET_LINES` |
| `ModuleNotFoundError` | Virtual environment not activated | Run `source venv/bin/activate` |
| `PermissionError` | No write permission for log/state files | Change the paths in `config.py` to a writable location |

---

## Changing the Area Code (Kansai / Tokai)

You can monitor Kansai (Osaka area) and Tokai (Nagoya area) regions by changing `AREA_CODE` in `config.py`:

| Region | AREA_CODE |
|--------|-----------|
| Kanto (Tokyo area) | `"4"` |
| Tokai (Nagoya area) | `"5"` |
| Kansai (Osaka area) | `"6"` |
