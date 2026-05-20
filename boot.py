import network
import time
import machine
from machine import Pin

# ── Configuración WiFi ───────────────────────────────────────
WIFI_SSID = 'Cudy-0138'
WIFI_PASS = '41659458'

# ── LED de estado ────────────────────────────────────────────
led = Pin(2, Pin.OUT)

def blink(times=3, delay=0.15):
    """Parpadea el LED N veces para indicar estado."""
    for _ in range(times):
        led.on();  time.sleep(delay)
        led.off(); time.sleep(delay)

def conectar_wifi():
    """Conecta al WiFi previniendo el error de estado interno."""
    wlan = network.WLAN(network.STA_IF)

    # 1. FORZAR RESET DEL ESTADO INTERNO DEL WIFI
    print("[WiFi] Limpiando estado previo de la radio...")
    wlan.active(False)   # Desactivar por completo
    time.sleep(1)        # Pausa física para que el chip se apague

    # 2. ACTIVAR E INICIAR CONEXIÓN
    wlan.active(True)    # Volver a activar de forma limpia

    if wlan.isconnected():
        print("[WiFi] Ya conectado:", wlan.ifconfig()[0])
        led.on()
        return

    print("[WiFi] Conectando a '{}' ...".format(WIFI_SSID))
    wlan.connect(WIFI_SSID, WIFI_PASS)

    # Contador de intentos para evitar bucles infinitos
    for intento in range(20):
        if wlan.isconnected():
            break
        blink(1, 0.4)
        print("[WiFi] Intento {}/20 ...".format(intento + 1))
        time.sleep(0.5)

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print('=============================================')
        print('  GRUA TORRE - Servidor Web ESP32')
        print('  IP:', ip)
        print('  URL: http://' + ip)
        print('=============================================')
        blink(3, 0.1)
        led.on()
    else:
        print("[WiFi] Error: No se pudo conectar. Verifica SSID/Contrasena.")
        print("[WiFi] Reiniciando placa para solucionar error de hardware...")
        time.sleep(2)
        machine.reset()

# ── Punto de entrada de boot.py ──────────────────────────────
# IMPORTANTE: boot.py SOLO conecta el WiFi.
# El servidor web completo se inicia en main.py automáticamente.
conectar_wifi()