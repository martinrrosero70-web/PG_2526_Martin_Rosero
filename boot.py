# ============================================================
#  GRUA TORRE - boot.py (Atenuación de Pico de Corriente - BOD)
# ============================================================
import network
import time
import sys
import uselect
import machine
from machine import Pin

RED_CASA = "Cudy-0138"
CLAVE_CASA = "41659458"

led_indicador = Pin(22, Pin.OUT)

def menu_inicio(timeout_segundos=5):
    print("\n" + "="*45)
    print("      SISTEMA DE CONTROL - GRÚA TORRE")
    print("="*45)
    print("1. Iniciar sistema normalmente (Modo Ejecución)")
    print("2. Detener en modo programación (Liberar REPL)")
    print("---------------------------------------------")
    try:
        poller = uselect.poll()
        poller.register(sys.stdin, uselect.POLLIN)
        tiempo_inicio = time.time()
        while (time.time() - tiempo_inicio) < timeout_segundos:
            if poller.poll(100):
                caracter = sys.stdin.read(1)
                if caracter == '1':
                    return True
                elif caracter == '2':
                    print("\n[MODO PROGRAMACIÓN] REPL Liberado.")
                    return False
    except Exception as e:
        print(f"[BOOT] El modo de entrada no está disponible: {e}")
        print("[BOOT] Continuando con el arranque normal...")
    return True

if menu_inicio(timeout_segundos=5):
    print("\n[Radio] Inicializando modo de red seguro...")
    machine.freq(80000000)  # Reduce consumo inicial del ESP32 al arrancar
    wlan = network.WLAN(network.STA_IF)
    
    # Apagado total inicial para vaciar líneas de energía
    wlan.active(False)
    time.sleep(2.0)
    
    # Encendido progresivo
    wlan.active(True)
    time.sleep(2.5)  # Espera adicional para estabilizar el módulo WiFi
    
    # EVITAMOS el scan() para no disparar el consumo al 100%
    print(f"[WiFi] Intentando enlace directo a: '{RED_CASA}'")
    try:
        wlan.connect(RED_CASA, CLAVE_CASA)
        
        intentos = 0
        max_intentos = 40
        while not wlan.isconnected() and intentos < max_intentos:
            # Hacemos parpadear el LED de forma intermitente suave
            led_indicador.value(1)
            time.sleep(0.1)
            led_indicador.value(0)
            time.sleep(0.4)
            
            print(f" Conectando... ({intentos+1}/{max_intentos})")
            intentos += 1
            
        if wlan.isconnected():
            led_indicador.value(1) # Fijo al estar conectado
            print("\n" + "="*45)
            print("  ¡CONECTADO AL ENRUTADOR CUDY!")
            print(f"  IP Asignada: {wlan.ifconfig()[0]}")
            print("="*45)
        else:
            led_indicador.value(0)
            print("\n[WiFi] Tiempo de espera agotado sin conexión.")
            print("[WiFi] Activando modo punto de acceso local...")
            wlan.active(False)
            ap = network.WLAN(network.AP_IF)
            ap.active(True)
            ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
            ap.config(essid="GRUA_TORRE", password="12345678", authmode=3)
            time.sleep(1.0)
            print("\n" + "="*45)
            print("  AP local activo: 'GRUA_TORRE'")
            print(f"  IP Asignada: {ap.ifconfig()[0]}")
            print("="*45)
    except Exception as e:
        led_indicador.value(0)
        print(f"\n[WiFi] Error durante la autenticación: {e}")
        print("[WiFi] Activando modo punto de acceso local...")
        wlan.active(False)
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
        ap.config(essid="GRUA_TORRE", password="12345678", authmode=3)
        time.sleep(1.0)
        print("\n" + "="*45)
        print("  AP local activo: 'GRUA_TORRE'")
        print(f"  IP Asignada: {ap.ifconfig()[0]}")
        print("="*45)
else:
    sys.exit()