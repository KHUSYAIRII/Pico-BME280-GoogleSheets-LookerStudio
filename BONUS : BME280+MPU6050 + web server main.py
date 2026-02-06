from machine import Pin, I2C, PWM
import network, time, socket, gc
import ssd1306, bme280, urequests
from imu import MPU6050

# ---------------- CONFIGURATION ----------------
# PASTE YOUR GOOGLE APPS SCRIPT URL HERE:
GOOGLE_URL = ""

LOG_INTERVAL = 15000   # Upload to Cloud every 15s
READ_INTERVAL = 250    # Read sensors every 250ms

TEMP_LIMIT = 30.0      
HUM_LIMIT  = 60.0     
PRES_LIMIT = 1000.0   

wifi_ssid = ""
wifi_password = ""

# ---------------- HARDWARE SETUP ----------------
# I2C for OLED, BME280, MPU6050
i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000)
bme = bme280.BME280(i2c=i2c)
imu = MPU6050(i2c)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Indicators
led_red    = Pin(14, Pin.OUT)
led_yellow = Pin(13, Pin.OUT)
led_green  = Pin(12, Pin.OUT)

# Buzzer
buzzer = PWM(Pin(11))
buzzer.duty_u16(0)

# ---------------- ALERT LOGIC (Non-Blocking) ----------------
last_siren = 0
SIREN_COOLDOWN = 2000 # Play siren burst every 2 seconds max

def police_siren(now):
    global last_siren
    # Only play if enough time passed to keep loop responsive
    if time.ticks_diff(now, last_siren) > SIREN_COOLDOWN:
        buzzer.freq(700)
        buzzer.duty_u16(30000)
        time.sleep_ms(100) # Short block is acceptable for sound effect
        buzzer.freq(1400)
        time.sleep_ms(100)
        buzzer.duty_u16(0)
        last_siren = now

# ---------------- GOOGLE UPLOAD ----------------
def send_to_google(t, h, p, ax, ay, az):
    gc.collect() # Pre-request cleanup to free RAM
    print("Uploading to Cloud...")
    try:
        url = f"{GOOGLE_URL}?temp={t:.2f}&hum={h:.2f}&pres={p:.2f}&ax={ax:.2f}&ay={ay:.2f}&az={az:.2f}"
        r = urequests.get(url)
        r.close()
        
        # Success visual on OLED (top right pixel)
        oled.fill_rect(124, 0, 4, 4, 1)
        oled.show()
        print("Upload Success")
    except Exception as e:
        print("Upload Error:", e)
    gc.collect() # Post-request cleanup

# ---------------- WIFI CONNECTION ----------------
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(wifi_ssid, wifi_password)

oled.fill(0)
oled.text("Connecting WiFi...", 0, 0)
oled.show()

max_retries = 20
while max_retries > 0:
    if wlan.isconnected(): break
    max_retries -= 1
    time.sleep(1)

if wlan.isconnected():
    ip = wlan.ifconfig()[0]
    oled.fill(0)
    oled.text("WiFi Connected!", 0, 0)
    oled.text(ip, 0, 16)
    oled.show()
    print("IP:", ip)
    time.sleep(2)
else:
    print("WiFi Failed - Running Offline Mode")

# ---------------- WEB PAGE HTML ----------------
def web_page(t, h, p, ax, ay, az):
    return f"""<!DOCTYPE html>
<html>
<head>
<title>Pico Monitor</title>
<meta http-equiv="refresh" content="3">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: sans-serif; background: #6FA8FF; text-align: center; margin: 0; }}
.hill {{ position: fixed; bottom: -50px; left: -10%; width: 120%; height: 50vh; background: #8ADE61; border-top: 10px solid #00B050; transform: rotate(-5deg); z-index: -1; }}
.card {{ background: #FF8533; width: 80%; max-width: 350px; margin: 20px auto; padding: 15px; border-radius: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); border: 2px solid white; }}
h1 {{ color: white; text-shadow: 1px 1px 2px black; margin: 0; }}
p {{ font-size: 18px; font-weight: bold; margin: 5px 0; }}
.label {{ font-size: 12px; color: #333; }}
</style>
</head>
<body>
<div class="hill"></div>
<div class="card" style="background:#ff6600"><h1>System Status</h1><p style="color:white; font-size:12px">LIVE FEED</p></div>
<div class="card">
  <span class="label">Temperature</span><p>{t:.1f} &deg;C</p>
  <span class="label">Humidity</span><p>{h:.1f} %</p>
  <span class="label">Pressure</span><p>{p:.1f} hPa</p>
</div>
<div class="card">
  <span class="label">Acceleration (g)</span>
  <p>X: {ax:.2f} | Y: {ay:.2f}</p>
  <p>Z: {az:.2f}</p>
</div>
</body>
</html>"""

# ---------------- SERVER INIT ----------------
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)
s.setblocking(False)

# ---------------- MAIN LOOP ----------------
last_read = 0
last_log  = 0
temp = hum = pres = 0
ax = ay = az = 0

print(f"System Ready. Free RAM: {gc.mem_free()}")
gc.collect()

while True:
    now = time.ticks_ms()

    # --- 1. SENSOR READ & DISPLAY ---
    if time.ticks_diff(now, last_read) > READ_INTERVAL:
        try:
            # BME280 Reading
            t, p, h = bme.values
            temp = float(t.replace('C', ''))
            pres = float(p.replace('hPa', ''))
            hum  = float(h.replace('%', ''))

            # MPU6050 Reading
            ax = imu.accel.x
            ay = imu.accel.y
            az = imu.accel.z

            # Logic: Alert vs Normal
            if temp > TEMP_LIMIT:
                led_red.value(1)
                police_siren(now)
                oled.fill(0)
                oled.text("!!! HIGH TEMP !!!", 5, 25)
                oled.text(f"{temp:.1f} C", 40, 45)
            else:
                led_red.value(0)
                buzzer.duty_u16(0)
                
                # Normal OLED Display
                oled.fill(0)
                oled.text(f"T:{temp:.1f}C H:{hum:.0f}%", 0, 0)
                oled.text(f"P:{pres:.1f} hPa", 0, 15)
                oled.text(f"X:{ax:.2f} Y:{ay:.2f}", 0, 30)
                oled.text(f"Z:{az:.2f}", 0, 45)

            # LED Indicators
            led_yellow.value(1 if hum > HUM_LIMIT else 0)
            led_green.value(1 if pres > PRES_LIMIT else 0)

            oled.show()
            last_read = now

        except Exception as e:
            print("Sensor Error:", e)

    # --- 2. CLOUD UPLOAD ---
    if time.ticks_diff(now, last_log) > LOG_INTERVAL:
        if wlan.isconnected() and temp != 0:
            send_to_google(temp, hum, pres, ax, ay, az)
            last_log = now

    # --- 3. WEB SERVER ---
    try:
        conn, addr = s.accept()
        conn.settimeout(0.2) # Fast timeout to prevent blocking main loop
        request = conn.recv(1024)
        
        # Send Web Page
        response = web_page(temp, hum, pres, ax, ay, az)
        conn.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n')
        conn.sendall(response.encode())
        conn.close()
        gc.collect() # Clean up memory after large HTML string
        
    except OSError:
        pass
