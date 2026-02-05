# Pico-BME280-GoogleSheets-LookerStudio

# Raspberry Pi Pico / ESP32 Data Logger
This project reads temperature, humidity, and pressure from a BME280 sensor and uploads it to Google Sheets.

## Hardware Required
* Raspberry Pi Pico (or ESP32)
* BME280 Sensor
* Jumper Wires

## Wiring (Pico)
* **SDA:** Pin GP2
* **SCL:** Pin GP3
* **VCC:** 3.3V
* **GND:** GND

## How to use
1. Copy `bme280.py` to your device.
2. Open `main.py` and update these lines:
   ```python
   GOOGLE_URL = "PASTE_YOUR_URL_HERE"
   wifi_ssid = "YOUR_WIFI"
   wifi_password = "YOUR_PASSWORD"
