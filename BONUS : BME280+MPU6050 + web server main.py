from machine import Pin, I2C, PWM
import network
import time
import socket
import ssd1306
import bme280
import urequests
import gc  
from imu import MPU6050

# --- 1. CONFIGURATION ---
# PASTE YOUR GOOGLE APP SCRIPT URL INSIDE THE QUOTES BELOW:
GOOGLE_URL = "" 

LOG_INTERVAL = 15000  # Upload to Google every 15 seconds
TEMP_LIMIT = 30.0    
HUM_LIMIT = 60.0     
PRES_LIMIT = 1000.0 

wifi_ssid = ""
wifi_password = ""

# --- 2. HARDWARE INITIALIZATION ---
i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000) 
bme = bme280.BME280(i2c=i2c)
imu = MPU6050(i2c)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# LED Setup
led_red = Pin(14, Pin.OUT)    
led_yellow = Pin(13, Pin.OUT) 
led_green = Pin(12, Pin.OUT)  

# Buzzer Setup
buzzer = PWM(Pin(11))
buzzer.duty_u16(0) 

# --- 3. HELPER FUNCTIONS ---
def play_police_siren():
    buzzer.freq(600)
    buzzer.duty_u16(30000)
    time.sleep(0.05)
    buzzer.freq(1200)
    buzzer.duty_u16(30000)
    time.sleep(0.05)
    buzzer.duty_u16(0)

def send_to_google(t, h, p, x, y, z):
    """Sends sensor data to Google Sheets with Memory Protection"""
    print("Uploading to Google Sheets...")
    
    # 1. CLEAN MEMORY BEFORE CONNECTING
    gc.collect() 
    
    url = f"{GOOGLE_URL}?temp={t}&hum={h}&pres={p}&ax={x}&ay={y}&az={z}"
    
    try:
        # 2. Send Request
        response = urequests.get(url)
        print(f"Status: {response.status_code} (Text: {response.text})")
        
        # 3. CLOSE IMMEDIATELY TO FREE RAM
        response.close()
        
        # Indicate success on OLED (small dot top right)
        oled.fill_rect(124, 0, 4, 4, 1) 
        oled.show()
        
    except Exception as e:
        print("Upload Error:", e)
    
    # 4. CLEAN MEMORY AFTER CONNECTING
    gc.collect()

# --- 4. WIFI CONNECT ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(wifi_ssid, wifi_password)

oled.fill(0)
oled.text("Connecting...", 0, 0)
oled.show()

max_wait = 10
while max_wait > 0:
    if wlan.isconnected():
        break
    max_wait -= 1
    time.sleep(1)

if wlan.isconnected():
    ip_address = wlan.ifconfig()[0]
    print(f"\nConnected! IP: {ip_address}")
    oled.fill(0)
    oled.text("WiFi Connected!", 0, 0)
    oled.text(ip_address, 0, 16)
    oled.show()
    time.sleep(2) 
else:
    ip_address = "OFFLINE"
    print("Wifi Failed")

# --- 5. WEB PAGE GENERATOR ---
# --- 5. UPDATED WEB PAGE GENERATOR (Directly on Pico) ---
def web_page(temp, hum, pres, ax, ay, az):
    # Note: In Python f-strings, CSS brackets {} must be doubled {{ }}
    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <title>Pico Live Monitor</title>
        <meta http-equiv="refresh" content="2">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 0; background-color: #6FA8FF; text-align: center; overflow-x: hidden; }}
            
            /* The Hill Design */
            .hill {{ 
                position: fixed; bottom: -220px; left: -100px; width: 150%; height: 80vh; 
                background-color: #8ADE61; border-top: 40px solid #00B050; 
                transform: rotate(-15deg); z-index: -1; 
            }}
            
            .container {{ padding-top: 30px; display: flex; flex-direction: column; align-items: center; gap: 20px; }}
            
            /* Cards Design */
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

# --- 6. SERVER SETUP ---
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)
s.setblocking(False)

# --- 7. MAIN LOOP ---
last_read_time = 0
read_interval = 250 

last_log_time = 0 
temp, hum, pres = 0, 0, 0
ax, ay, az = 0, 0, 0

print(f"Loop Started. Free RAM: {gc.mem_free()}")
gc.collect()

while True:
    current_time = time.ticks_ms()

    # --- A. SENSOR & DISPLAY ---
    if time.ticks_diff(current_time, last_read_time) >= read_interval:
        try:
            # 1. Read Sensors
            t, p, h = bme.values 
            temp = float(t.replace('C', ''))
            pres = float(p.replace('hPa', ''))
            hum = float(h.replace('%', ''))
            
            ax = imu.accel.x
            ay = imu.accel.y
            az = imu.accel.z
            
            # 2. ALERTS
            if temp > TEMP_LIMIT:
                led_red.value(1)
                play_police_siren()
                oled.fill(0)
                oled.text("! HIGH TEMP !", 15, 25)
                oled.text(f"{temp:.1f} C", 40, 40)
            
            else:
                led_red.value(0)
                buzzer.duty_u16(0)

            led_yellow.value(1) if hum > HUM_LIMIT else led_yellow.value(0)
            led_green.value(1) if pres > PRES_LIMIT else led_green.value(0)

            # 3. OLED UPDATE
            oled.fill(0)
            oled.text(f"T:{temp:.1f}C H:{hum:.0f}%", 0, 0)
            oled.text(f"P:{pres:.1f} hPa", 0, 15)
            oled.text(f"X:{ax:.2f} Y:{ay:.2f}", 0, 30)
            oled.text(f"Z:{ay:.2f}", 0, 45)
            
            
                
            
            oled.show()
            last_read_time = current_time

        except Exception as e:
            print(f"Sensor Error: {e}")

    # --- B. GOOGLE SHEETS LOGGING ---
    if time.ticks_diff(current_time, last_log_time) >= LOG_INTERVAL:
        if wlan.isconnected() and temp != 0:
            send_to_google(temp, hum, pres, ax, ay, az)
            last_log_time = current_time

    # --- C. WEB SERVER ---
    try:
        conn, addr = s.accept()
        request = conn.recv(1024)
        response = web_page(temp, hum, pres, ax, ay, az)
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall(response)
        conn.close()
        
        # Clean memory after serving a big HTML page
        gc.collect()
        
    except OSError:
        pass

