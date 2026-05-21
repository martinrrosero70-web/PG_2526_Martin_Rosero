import network
import time
import uasyncio as asyncio
from machine import Pin, UART

# =============================================================================
# CONFIGURACIÓN DE RED
# =============================================================================
RED_CASA = "Moises"
CLAVE_CASA = "1357924609moi"

led_indicador = Pin(2, Pin.OUT)

# ── UART hacia Arduino Nano ──────────────────────────────────
uart = UART(2, baudrate=9600, tx=17, rx=16)

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep(1) 
    if not wlan.isconnected():
        print("Conectando a la red Wi-Fi...", end="")
        wlan.connect(RED_CASA, CLAVE_CASA)
        intentos = 0
        while not wlan.isconnected() and intentos < 30:
            led_indicador.value(not led_indicador.value())
            time.sleep(0.5)
            print(".", end="")
            intentos += 1
            
    if wlan.isconnected():
        led_indicador.value(1)
        config = wlan.ifconfig()
        return config[0]
    else:
        led_indicador.value(0)
        return "0.0.0.0"

# Guardamos el HTML en una sola línea sólida para evitar errores de sintaxis
def obtener_html():
    return "<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Control Grua Torre</title><style>body { font-family: Arial; text-align: center; background-color: #222; color: #fff; } h1 { color: #ffcc00; } .btn { display: inline-block; padding: 15px 25px; font-size: 18px; margin: 10px; cursor: pointer; background-color: #444; color: white; border: 2px solid #ffcc00; border-radius: 8px; width: 120px; } .btn:active { background-color: #ffcc00; color: black; } .stop { background-color: #aa0000; border-color: #ff3333; } .stop:active { background-color: #ff3333; }</style></head><body><h1>🏗️ CONTROL GRÚA TORRE</h1><p>Utiliza los botones para operar el sistema.</p><hr color='#ffcc00'><div><button class='btn' onclick=\"fetch('/subir')\">⬆️ Subir</button></div><div><button class='btn' onclick=\"fetch('/izquierda')\">⬅️ Izquierda</button><button class='btn stop' onclick=\"fetch('/parar')\">🛑 PARAR</button><button class='btn' onclick=\"fetch('/derecha')\">Derecha ➡️</button></div><div><button class='btn' onclick=\"fetch('/bajar')\">⬇️ Bajar</button></div></body></html>"

async def handle_client(reader, writer):
    try:
        request_line = await reader.readline()
        request = request_line.decode("utf-8")
        while True:
            line = await reader.readline()
            if line == b"\r\n" or line == b"\n" or not line:
                break
        
        if "GET /subir" in request:
            print("[Acción] Grúa subiendo...")
            uart.write("U")
        elif "GET /bajar" in request:
            print("[Acción] Grúa bajando...")
            uart.write("D")
        elif "GET /izquierda" in request:
            print("[Acción] Girando a la izquierda...")
            uart.write("L")
        elif "GET /derecha" in request:
            print("[Acción] Girando a la derecha...")
            uart.write("R")
        elif "GET /parar" in request:
            print("[Acción] 🛑 Sistema Detenido.")
            uart.write("S")
            
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n" + obtener_html()
        writer.write(response.encode("utf-8"))
        await writer.drain()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await writer.close()

async def main(ip_asignada):
    print("\n=============================================")
    print("  GRUA TORRE - Servidor Web ESP32")
    print(f"  IP: {ip_asignada}")
    print(f"  URL: http://{ip_asignada}")
    print("=============================================")
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    while True:
        await asyncio.sleep(3600)

# Lanzamiento limpio del script
ip = conectar_wifi()
if ip != "0.0.0.0":
    try:
        asyncio.run(main(ip))
    except KeyboardInterrupt:
        print("\nServidor apagado.")
else:
    print("\nError: No se conectó al Wi-Fi.")
