from machine import Pin, I2C
import network   # Allowing the device to connect to wireless
import time
import bme280
import urequests # Enable your Python program to easily make HTTP requests
import gc        # Garbage Collector: Frees up unused RAM to prevent crashes

# --- CONFIGURATION ---

GOOGLE_URL = "PASTE_YOUR_GOOGLE_SCRIPT_URL_HERE" 

# Time between uploads in milliseconds (15000ms = 15 seconds)
# ! WARNING: Setting this too low may crash the device due to memory overload
LOG_INTERVAL = 15000  

wifi_ssid = "YOUR_WIFI_NAME"
wifi_password = "YOUR_WIFI_PASSWORD"

# --- HARDWARE INITIALIZATION ---
# Initialize I2C communication (GPIO 2 & 3)
i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000) 
bme = bme280.BME280(i2c=i2c)

# --- FUNCTIONS ---
def connect_wifi():
    """
    Handles connecting (and reconnecting) to WiFi.
    This function is called at the start and whenever the connection is lost.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(wifi_ssid, wifi_password)
        
        # Wait for connection with a timeout
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            
    if wlan.isconnected():
        print(f"WiFi Connected! IP: {wlan.ifconfig()[0]}")
        return True
    else:
        print("WiFi Connection Failed. Please check your credentials.")
        return False

def send_to_google(temp_val, hum_val, pres_val):
    """
    Sends sensor data to Google Sheets via HTTP GET request.
    """
    print("Uploading to Google Sheets...")
    
    # 1. Free up memory before the request to prevent crashes
    gc.collect() 
    
    # Safety Check: Stop if the user forgot to paste the URL
    if "script.google.com" not in GOOGLE_URL:
        print("Error: Google URL not set!")
        return

    # 2. Construct the URL
    # We explicitly map variables to ensure Humidity goes to 'hum' and Pressure to 'pres'
    url = f"{GOOGLE_URL}?temp={temp_val}&hum={hum_val}&pres={pres_val}"
    
    try:
        response = urequests.get(url)
        print(f"Status: {response.status_code} (Text: {response.text})")
        response.close() # Close connection to free RAM
    except Exception as e:
        print("Upload Error:", e)
    
    # 3. Free up memory again after the request
    gc.collect()

# --- INITIAL SETUP ---
# Try to connect to WiFi before starting the main loop
connect_wifi()

# --- MAIN LOOP ---
last_log_time = 0 
print("Starting Sensor Loop...")

while True:
    current_time = time.ticks_ms()
    
    try:
        # 1. READ BME280 DATA
        # The library returns 3 values in this specific order: Temp, Pressure, Humidity
        raw_t, raw_p, raw_h = bme.values 
        
        # Clean the data (remove units like 'C', '%', 'hPa')
        # We assign them to named variables so we don't mix them up later
        temp = float(raw_t.replace('C', ''))
        pres = float(raw_p.replace('hPa', ''))
        hum = float(raw_h.replace('%', ''))

        # 2. CHECK TIME & UPLOAD
        # Check if 15 seconds have passed since the last upload
        if time.ticks_diff(current_time, last_log_time) >= LOG_INTERVAL:
            
            # Check connection before uploading
            wlan = network.WLAN(network.STA_IF)
            
            # Automatic Reconnect Logic: If WiFi dropped, try to fix it
            if not wlan.isconnected():
                print("WiFi lost! Attempting to reconnect...")
                connect_wifi()
            
            # Only upload if the reconnect worked
            if wlan.isconnected():
                send_to_google(temp, hum, pres)
                last_log_time = current_time
            else:
                print("Skipping upload (No WiFi).")

    except Exception as e:
        print(f"Sensor Loop Error: {e}")
    
    # Small delay to prevent CPU overload
    time.sleep(0.1)
