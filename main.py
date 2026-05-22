# ============================================================
#  GRUA TORRE - main.py (Servidor Web para DevKit V1)
# ============================================================
import uasyncio as asyncio
import network
import ujson
from machine import UART, Pin
import time

# UART 2 física: TX=GPIO 17 directo al RX del Arduino Nano (con tu divisor de tensión)
uart = UART(2, baudrate=9600, tx=17, rx=16)
led = Pin(2, Pin.OUT) # Controla el LED azul de tu DevKit V1

last_cmd = "S"
telemetry = {
    "start_ms": time.ticks_ms(),
    "commands": {"F": 0, "B": 0, "U": 0, "D": 0, "L": 0, "R": 0, "S": 0},
    "http_requests": 0,
    "http_errors": 0,
    "last_error": None,
}

def obtener_html():
    return """<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Control Grúa Torre</title><style>body { font-family: Arial, sans-serif; text-align: center; background: #f4f4f9; margin: 0; padding: 20px; } h1 { color: #333; } .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; max-width: 400px; margin: 20px auto; } button { padding: 20px; font-size: 18px; font-weight: bold; border: none; border-radius: 8px; background: #3498db; color: white; cursor: pointer; transition: 0.2s; } button:active { background: #2980b9; transform: scale(0.95); } .stop { grid-column: span 2; background: #e74c3c; } .stop:active { background: #c0392b; } .status { margin-top: 20px; font-size: 14px; color: #666; }</style></head><body><h1>🏗️ Panel Grúa Torre</h1><div class='grid'><button onclick='send("U")'>⬆️ Subir</button><button onclick='send("F")'>🚜 Adelante</button><button onclick='send("D")'>⬇️ Bajar</button><button onclick='send("B")'>🚜 Atrás</button><button onclick='send("L")'>🔄 Izquierda</button><button onclick='send("R")'>🔄 Derecha</button><button class='stop' onclick='send("S")'>🛑 PARAR</button></div><div class='status'>Último comando: <span id='cmd'>Ninguno</span></div><script>function send(c){fetch('/cmd?c='+c,{method:'POST'}).then(()=>document.getElementById('cmd').innerText=c);}</script></body></html>"""

def get_local_ip():
    wlan = network.WLAN(network.STA_IF)
    if wlan.active() and wlan.isconnected():
        return wlan.ifconfig()[0]
    ap = network.WLAN(network.AP_IF)
    if ap.active():
        return ap.ifconfig()[0]
    return "0.0.0.0"


def get_uptime_seconds():
    return time.ticks_diff(time.ticks_ms(), telemetry["start_ms"]) / 1000.0


def parse_request_line(request_line):
    try:
        line = request_line.decode("utf-8").strip()
        parts = line.split()
        if len(parts) >= 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return None, None


def ensure_network():
    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)
    if sta.active() and sta.isconnected():
        return sta.ifconfig()[0], "STA"
    if not ap.active():
        print("[NETWORK] No hay STA activa. Iniciando AP local...")
        ap.active(True)
        ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
        ap.config(essid="GRUA_TORRE", password="12345678", authmode=3)
        time.sleep(1.0)
    if ap.active():
        return ap.ifconfig()[0], "AP"
    return "0.0.0.0", "NONE"

def debug_network_status():
    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)
    print("[NETWORK] STA active:", sta.active(), "connected:", sta.isconnected(), "IP:", sta.ifconfig()[0] if sta.active() else "-")
    print("[NETWORK] AP active:", ap.active(), "IP:", ap.ifconfig()[0] if ap.active() else "-")
    if ap.active():
        print("[NETWORK] AP SSID:", ap.config('essid'))

# ── PROCESADOR HTTP ASÍNCRONO SEGURO ──────────────────────────
async def handle_client(reader, writer):
    global last_cmd
    telemetry["http_requests"] += 1
    try:
        request_line = await reader.readline()
        if not request_line:
            return

        method, path = parse_request_line(request_line)
        if not method or not path:
            return

        # Consumir todas las cabeceras entrantes para liberar el búfer del socket
        while True:
            line = await reader.readline()
            if line == b"\r\n" or line == b"\n" or not line:
                break

        # Servir Interfaz Web HTML
        if method == "GET" and path in ["/", "/index.html"]:
            body = obtener_html()
            response = ("HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/html; charset=utf-8\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n\r\n" + body).format(len(body.encode('utf-8')))
            writer.write(response.encode('utf-8'))

        # Inyección de comandos por botones hacia UART
        elif method == "POST" and path.startswith("/cmd?c="):
            c = path[path.find("?c=") + 3:path.find("?c=") + 4].upper()
            if c in ["F", "B", "U", "D", "L", "R", "S"]:
                last_cmd = c
                telemetry["commands"][c] += 1
                uart.write(c.encode())
                led.value(0 if c == "S" else 1)

                body = ujson.dumps({"status": "ok", "command": c})
                response = ("HTTP/1.1 200 OK\r\n"
                            "Content-Type: application/json\r\n"
                            "Content-Length: {}\r\n"
                            "Connection: close\r\n\r\n" + body).format(len(body))
                writer.write(response.encode())
            else:
                body = ujson.dumps({"status": "error", "error": "Comando inválido"})
                response = ("HTTP/1.1 400 Bad Request\r\n"
                            "Content-Type: application/json\r\n"
                            "Content-Length: {}\r\n"
                            "Connection: close\r\n\r\n" + body).format(len(body))
                writer.write(response.encode())

        # Endpoint de telemetría y verificación rápida
        elif method == "GET" and path == "/status":
            body = ujson.dumps({
                "ip": get_local_ip(),
                "last_cmd": last_cmd,
                "uptime_s": get_uptime_seconds(),
                "http_requests": telemetry["http_requests"],
                "http_errors": telemetry["http_errors"],
            })
            response = ("HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/json\r\n"
                        "Content-Length: {}\r\n"
                        "Connection: close\r\n\r\n" + body).format(len(body))
            writer.write(response.encode())
        else:
            writer.write(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")

        await writer.drain() # Forzar salida inmediata de paquetes TCP

    except Exception as e:
        telemetry["http_errors"] += 1
        telemetry["last_error"] = str(e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass

# ── ENLACE DIRECTO DE RED ────────────────────────────────────
async def main():
    ip, mode = ensure_network()
    print("=" * 45)
    print("  GRUA TORRE - Servidor Servido de Forma Asíncrona")
    print("  Modo de red:", mode)
    print("  IP Local:", ip)
    debug_network_status()
    
    bind_ip = "0.0.0.0"
    if ip != "0.0.0.0":
        print("  URL Control: http://{}".format(ip))
        if mode == "AP":
            print("  Conéctate al SSID: GRUA_TORRE")
    else:
        print("  [ERROR] No se pudo obtener IP de red.")
        if mode == "NONE":
            print("  Comprueba el módulo WiFi y la alimentación.")
    print("=" * 45)
    try:
        server = await asyncio.start_server(handle_client, bind_ip, 80)
        print(f"[HTTP] Servidor HTTP iniciado en {bind_ip}:80")
        while True:
            await asyncio.sleep(3600)
    except Exception as e:
        print("[ERROR] No se pudo iniciar servidor HTTP:", e)
        print("  Verifica alimentación y la interfaz de red antes de volver a intentar.")

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\n[INFO] Servidor web detenido correctamente.")