# ============================================================
#  GRUA TORRE - boot.py  (ESP32 MicroPython)
# ============================================================
#  Configura WiFi antes de arrancar main.py.
#  Editar SSID y PASSWORD antes de flashear.
# ============================================================

import network
import time
from machine import Pin

WIFI_SSID     = "TU_RED_WIFI"    # <-- CAMBIAR
WIFI_PASSWORD = "TU_CONTRASENA"  # <-- CAMBIAR

led = Pin(2, Pin.OUT)

def blink(times=3, delay=0.15):
    for _ in range(times):
        led.on();  time.sleep(delay)
        led.off(); time.sleep(delay)

def connect_wifi(ssid, password, retries=10):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        print("[WiFi] Ya conectado:", wlan.ifconfig()[0])
        led.on()
        return wlan.ifconfig()[0]
    print("[WiFi] Conectando a '{}' ...".format(ssid))
    wlan.connect(ssid, password)
    for attempt in range(retries):
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            print("[WiFi] Conectado! IP:", ip)
            blink(3, 0.1)
            led.on()
            return ip
        blink(1, 0.4)
        print("[WiFi] Intento {}/{} ...".format(attempt + 1, retries))
        time.sleep(1)
    led.off()
    raise RuntimeError("[WiFi] Sin conexion tras {} intentos.".format(retries))

try:
    connect_wifi(WIFI_SSID, WIFI_PASSWORD)
except RuntimeError as e:
    print(e)
