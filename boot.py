import network
import time
from machine import Pin

RED_CASA = "Cudy-0138"
CLAVE_CASA = "41659458"

led_pin = Pin(22, Pin.OUT)

print("[BOOT] Inicializando conexion WiFi...")

wlan = network.WLAN(network.STA_IF)
wlan.active(False)
time.sleep(1.0)

wlan.active(True)
time.sleep(2.0)

print("[BOOT] Conectando a: {}".format(RED_CASA))

try:
    wlan.connect(RED_CASA, CLAVE_CASA)
    
    intentos = 0
    max_intentos = 20
    
    while not wlan.isconnected() and intentos < max_intentos:
        led_pin.value(1)
        time.sleep(0.2)
        led_pin.value(0)
        time.sleep(0.3)
        intentos += 1
        print("[BOOT] Intentando conexion... ({}/{})".format(intentos, max_intentos))
    
    if wlan.isconnected():
        led_pin.value(1)
        print("[BOOT] OK - WiFi conectado!")
        print("[BOOT] IP: {}".format(wlan.ifconfig()[0]))
    else:
        led_pin.value(0)
        print("[BOOT] ERROR - No se pudo conectar a WiFi")
        print("[BOOT] Verifica SSID y contrasena")
        
except Exception as e:
    led_pin.value(0)
    print("[BOOT] ERROR: {}".format(e))
