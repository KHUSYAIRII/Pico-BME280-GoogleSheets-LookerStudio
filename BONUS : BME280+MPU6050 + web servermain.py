from machine import Pin, I2C, PWM
import network
import time
import socket
import ssd1306
import bme280
import urequests
import gc  # Garbage Collector is used for free up RAM
from imu import MPU6050

# --- CONFIGURATION ---
# This URL is where data will be sent to the Google Sheet
GOOGLE_URL = "https://script.google.com/macros/s/AKfycbxVmd-M-2DE56jxGkpRa7ogcK2OY1-HfrWfA6c0gyLb6cNz612UJZObapxlOXHD7MyaAA/exec" 

LOG_INTERVAL = 15000  # 15 seconds between data uploads to Google Sheet
TEMP_LIMIT = 30.0     # Temperature limit for Red LED + Buzzer to response
HUM_LIMIT = 60.0      # Humidity limit for Yellow LED to response
PRES_LIMIT = 1000.0   # Pressure limit for Green LED to response

wifi_ssid = "Nafh"
wifi_password = "1234567809"

# --- HARDWARE INITIALIZATION ---
# Initialize I2C communication on Bus 1, using GPIO 2 and GPIO 3
i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000) 

# Initialize sensor using the I2C bus created above
bme = bme280.BME280(i2c=i2c)            # Temperature/Humidity/Pressure Sensor
imu = MPU6050(i2c)                      # Gyroscope/Accelerometer Sensor
oled = ssd1306.SSD1306_I2C(128, 64, i2c) # 128x64 OLED Display

# Setup LED GPIO
led_red = Pin(14, Pin.OUT)     
led_yellow = Pin(13, Pin.OUT) 
led_green = Pin(12, Pin.OUT)  

# Setup Buzzer GPIO and PWM (Pulse Width Modulation) on Pin 11 for sound
buzzer = PWM(Pin(11))
buzzer.duty_u16(0) # Start the Buzzer with volume cycle at 0 (Silent)

# --- FUNCTIONS ---
def play_police_siren():
    """
    Modulates the buzzer frequency to mimic a siren sound.
    Alternates between 600Hz and 1200Hz.
    """
    buzzer.freq(600)            # Low tone
    buzzer.duty_u16(30000)      # Set volume
    time.sleep(0.05)            # Hold tone
    buzzer.freq(1200)           # High tone
    buzzer.duty_u16(30000)      # Set volume
    time.sleep(0.05)            # Hold tone
    buzzer.duty_u16(0)          # Silence

def send_to_google(t, h, p, x, y, z):
    """
    Sends sensor data to Google Sheets via HTTP GET request.
    Includes memory protection using Garbage Collection (gc).
    """
    print("Uploading to Google Sheets...")
    
    # Clean bemory before connecting
    # Clearing unused variables first to prevents from crashes
    gc.collect() 
    
    # Construct the URL with query parameters
    url = f"{GOOGLE_URL}?temp={t}&hum={h}&pres={p}&ax={x}&ay={y}&az={z}"
    
    try:
        # Send Request
        response = urequests.get(url)
        print(f"Status: {response.status_code} (Text: {response.text})")
        
        # Close to free up the RAM
        # If the socket isn't closed to free up the RAM, the Pico will run out of RAM quickly
        response.close()
        
        # Create the 4x4 pixel dot in the top right corner to show the success on OLED
        oled.fill_rect(124, 0, 4, 4, 1) 
        oled.show()
        
    except Exception as e:
        print("Upload Error:", e)
    
    # Clean memory after connecting
    # Clean up any temporary variables created during the request
    gc.collect()

# --- WIFI CONNECTION ---
# Initialize Wi-Fi interface
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(wifi_ssid, wifi_password)

# Display "Connecting" status on OLED
oled.fill(0)
oled.text("Connecting...", 0, 0)
oled.show()

# Wait for connection with a timeout counter
max_wait = 10
while max_wait > 0:
    if wlan.isconnected():
        break
    max_wait -= 1
    time.sleep(1)

# Check final connection status and display IP address
if wlan.isconnected():
    ip_address = wlan.ifconfig()[0] # Get the IP assigned by the router
    print(f"\nConnected! IP: {ip_address}")
    oled.fill(0)
    oled.text("WiFi Connected!", 0, 0)
    oled.text(ip_address, 0, 16)
    oled.show()
    time.sleep(2) 
else:
    ip_address = "OFFLINE"
    print("Wifi Failed")

# --- WEB PAGE GENERATOR ---
# Updated web page generator diirectly on Pico
def web_page(temp, hum, pres, ax, ay, az):
    """
    Generates an HTML string with embedded CSS styles.
    Injects current sensor variables into the HTML using f-strings.
    Note: CSS curly braces {} are escaped as {{ }} in Python f-strings.
    """
    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <title>Pico Live Monitor</title>
        <meta http-equiv="refresh" content="2">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 0; background-color: #6FA8FF; text-align: center; overflow-x: hidden; }}
            
            /* The Hill Design (Visual Styling) */
            .hill {{ 
                position: fixed; bottom: -220px; left: -100px; width: 150%; height: 80vh; 
                background-color: #8ADE61; border-top: 40px solid #00B050; 
                transform: rotate(-15deg); z-index: -1; 
            }}
            
            .container {{ padding-top: 30px; display: flex; flex-direction: column; align-items: center; gap: 20px; }}
            
            /* Cards Design (Data Containers) */
            .card {{ 
                background-color: #FF8533; color: black; width: 85%; max-width: 350px; 
                padding: 20px; border-radius: 25px; 
                box-shadow: 0 4px 8px rgba(0,0,0,0.2); 
                border: 2px solid white;
            }}
            
            h1 {{ margin: 0; color: white; text-shadow: 1px 1px 2px black; font-size: 28px; }}
            p {{ margin: 10px 0; font-size: 20px; font-weight: bold; }}
            .label {{ font-size: 14px; color: #333; font-weight: normal; }}
        </style>
    </head>
    <body>
        <div class="hill"></div>
        <div class="container">
            
            <div class="card" style="background-color: #ff6600;">
                <h1>Monitor Library</h1>
                <p style="font-size:14px; color:white;">LIVE DIRECT FEED</p>
            </div>

            <div class="card">
                <span class="label">Temperature</span>
                <p>{temp:.1f} &deg;C</p>
                <hr style="border: 1px dashed black; opacity: 0.3;">
                <span class="label">Humidity</span>
                <p>{hum:.1f} %</p>
                <hr style="border: 1px dashed black; opacity: 0.3;">
                <span class="label">Pressure</span>
                <p>{pres:.1f} hPa</p>
            </div>

            <div class="card">
                <p style="text-decoration: underline;">Gyroscope</p>
                <p>X: {ax:.2f}</p>
                <p>Y: {ay:.2f}</p>
                <p>Z: {az:.2f}</p>
            </div>
            
        </div>
    </body>
    </html>
    """
    return html

# --- SERVER SETUP ---
# Create a socket for the web server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80)) # Bind to port 80 (Standard Universal Port)
s.listen(5)      # Allow up to 5 devices to 'wait in line' if the Pico is busy
s.setblocking(False) # Non Blocking is used for continues loop even if no one visits the website

# --- MAIN LOOP ---
last_read_time = 0
read_interval = 250 # Update sensors every 250ms

last_log_time = 0 
temp, hum, pres = 0, 0, 0
ax, ay, az = 0, 0, 0

print(f"Loop Started. Free RAM: {gc.mem_free()}")
gc.collect()

while True:
    current_time = time.ticks_ms() # Get current uptime in milliseconds

    # --- SENSOR & DISPLAY ---
    # Non-blocking timer is uesd to check if 250ms has passed since last read
    if time.ticks_diff(current_time, last_read_time) >= read_interval:
        try:
            # Read Sensors
            t, p, h = bme.values 
            # BME returns strings like "25C", so we remove units to get float numbers
            temp = float(t.replace('C', ''))
            pres = float(p.replace('hPa', ''))
            hum = float(h.replace('%', ''))
            
            # Read IMU (Gyro/Accel) data
            ax = imu.accel.x
            ay = imu.accel.y
            az = imu.accel.z
            
            # ALERTS LOGIC CHECK
            if temp > TEMP_LIMIT:
                led_red.value(1)       # Turn ON Red LED
                play_police_siren()    # Activate Buzzer
                oled.fill(0)
                oled.text("! HIGH TEMP !", 15, 25)
                oled.text(f"{temp:.1f} C", 40, 40)
            
            else:
                led_red.value(0)       # Turn OFF Red LED
                buzzer.duty_u16(0)     # Silence Buzzer

            # Turn on Yellow LED if humidity > 60%
            led_yellow.value(1) if hum > HUM_LIMIT else led_yellow.value(0)
            # Turn on Green LED if pressure > 1000hPa
            led_green.value(1) if pres > PRES_LIMIT else led_green.value(0)

            # Update OLED
            oled.fill(0)
            oled.text(f"T:{temp:.1f}C H:{hum:.0f}%", 0, 0)
            oled.text(f"P:{pres:.1f} hPa", 0, 15)
            oled.text(f"X:{ax:.2f} Y:{ay:.2f}", 0, 30)
            oled.text(f"Z:{ay:.2f}", 0, 45)
            
            
                
            
            oled.show()
            last_read_time = current_time

        except Exception as e:
            print(f"Sensor Error: {e}")

    # --- GOOGLE SHEETS LOGGING ---
    # Check if 15 seconds (LOG_INTERVAL) have passed
    if time.ticks_diff(current_time, last_log_time) >= LOG_INTERVAL:
        # Only upload if connected to Wi-Fi and sensors have valid data
        if wlan.isconnected() and temp != 0:
            send_to_google(temp, hum, pres, ax, ay, az)
            last_log_time = current_time

    # --- WEB SERVER ---
    try:
        # Check if a web browser is trying to connect
        conn, addr = s.accept()
        request = conn.recv(1024) # Read the request
        
        # Generate the HTML with the latest sensor values
        response = web_page(temp, hum, pres, ax, ay, az)
        
        # Send HTTP headers and HTML content
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall(response)
        conn.close()
        
        # Clean memory after serving a big HTML page to prevent it from overflow
        gc.collect()
        
    except OSError:
        # Pass silently if no one is connecting (standard behavior for non-blocking sockets)
        pass
