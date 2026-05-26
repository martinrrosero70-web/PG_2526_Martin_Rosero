import uasyncio as asyncio
import network
import ujson
from machine import UART, Pin
import time

# Configuración de periféricos de la Grúa
uart = UART(2, baudrate=9600, tx=17, rx=16)
led = Pin(2, Pin.OUT)

last_cmd = "S"
telemetry = {
    "start_ms": time.ticks_ms(),
    "commands": {"F": 0, "B": 0, "U": 0, "D": 0, "L": 0, "R": 0, "S": 0},
    "http_requests": 0,
    "http_errors": 0,
}

def obtener_html():
    # Interfaz optimizada y limpia
    return """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Control Grua Torre</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { background: white; border-radius: 20px; padding: 30px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 400px; width: 100%; }
        h1 { text-align: center; color: #333; margin-bottom: 30px; font-size: 28px; }
        .control-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
        .btn { padding: 20px; font-size: 18px; font-weight: bold; border: none; border-radius: 12px; background: #3498db; color: white; cursor: pointer; transition: all 0.2s; touch-action: manipulation; }
        .btn:active { transform: scale(0.95); opacity: 0.8; }
        .btn-stop { grid-column: span 3; background: #e74c3c; font-size: 20px; padding: 25px; }
        .btn-stop:active { background: #c0392b; }
        .status { background: #ecf0f1; border-radius: 10px; padding: 15px; text-align: center; font-size: 14px; color: #555; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Grua Torre</h1>
        <div class="control-grid">
            <button class="btn" onclick="send('U')">Subir</button>
            <button class="btn" onclick="send('F')">Adelante</button>
            <button class="btn" onclick="send('D')">Bajar</button>
            <button class="btn" onclick="send('L')">Izq</button>
            <button class="btn" onclick="send('S')">Centro</button>
            <button class="btn" onclick="send('R')">Der</button>
            <button class="btn btn-stop" onclick="send('S')">PARAR</button>
        </div>
        <div class="status"><strong>Ultimo comando:</strong> <span id="cmd">-</span></div>
    </div>
    <script>
        function send(c){
            fetch('/cmd?c=' + c, { method: 'POST' })
            .then(r => r.json())
            .then(d => { document.getElementById('cmd').innerText = c; })
            .catch(e => console.error(e));
        }
    </script>
</body>
</html>"""

def parse_request_line(request_line):
    try:
        line = request_line.decode("utf-8").strip()
        parts = line.split()
        if len(parts) >= 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return None, None

def get_ip():
    wlan = network.WLAN(network.STA_IF)
    if wlan.active() and wlan.isconnected():
        return wlan.ifconfig()[0]
    return None

async def handle_client(reader, writer):
    global last_cmd
    telemetry["http_requests"] += 1
    linea_leida = b"" 
    
    try:
        request_line = await reader.readline()
        if not request_line:
            return

        linea_leida = request_line
        method, path = parse_request_line(request_line)
        
        if not method or method not in ["GET", "POST", "PUT", "DELETE"]:
            return

        # Vaciar cabeceras
        while True:
            line = await reader.readline()
            if line == b"\r\n" or line == b"\n" or not line:
                break

        # RUTA 1: Servir la interfaz Web principal
        if method == "GET" and path in ["/", "/index.html"]:
            body = obtener_html()
            body_bytes = body.encode('utf-8')
            
            # Formateamos SOLO la cabecera para evitar que interfiera con el CSS
            header = ("HTTP/1.1 200 OK\r\n"
                      "Content-Type: text/html; charset=utf-8\r\n"
                      "Content-Length: {}\r\n"
                      "Connection: close\r\n\r\n").format(len(body_bytes))
                      
            writer.write(header.encode('utf-8'))
            writer.write(body_bytes)

        # RUTA 2: Recepción de comandos de control
        elif method == "POST" and "/cmd?c=" in path:
            idx = path.find("?c=")
            c = path[idx + 3:idx + 4].upper()
            
            if c in ["F", "B", "U", "D", "L", "R", "S"]:
                last_cmd = c
                telemetry["commands"][c] += 1
                uart.write(c.encode())
                led.value(0 if c == "S" else 1)
                body = ujson.dumps({"status": "ok", "cmd": c})
            else:
                body = ujson.dumps({"status": "error", "msg": "comando invalido"})
            
            body_bytes = body.encode('utf-8')
            header = ("HTTP/1.1 200 OK\r\n"
                      "Content-Type: application/json\r\n"
                      "Content-Length: {}\r\n"
                      "Connection: close\r\n\r\n").format(len(body_bytes))
            
            writer.write(header.encode('utf-8'))
            writer.write(body_bytes)

        # RUTA 3: Panel de telemetría
        elif method == "GET" and path == "/status":
            body = ujson.dumps({
                "connected": True,
                "last_cmd": last_cmd,
                "uptime": int(time.ticks_diff(time.ticks_ms(), telemetry["start_ms"]) / 1000),
                "requests": telemetry["http_requests"],
            })
            body_bytes = body.encode('utf-8')
            header = ("HTTP/1.1 200 OK\r\n"
                      "Content-Type: application/json\r\n"
                      "Content-Length: {}\r\n"
                      "Connection: close\r\n\r\n").format(len(body_bytes))
            
            writer.write(header.encode('utf-8'))
            writer.write(body_bytes)
        
        else:
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")

        await writer.drain()

    except Exception as e:
        telemetry["http_errors"] += 1
        print("[ERROR CRÍTICO] Tipo: {}, Msg: {} en línea: {}".format(type(e).__name__, e, linea_leida))
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass

async def main():
    ip = get_ip()
    if not ip:
        print("[ERROR] No hay conexion WiFi disponible")
        return
    
    print("=" * 45)
    print("  SERVIDOR GRUA TORRE")
    print("  IP: http://{}".format(ip))
    print("=" * 45)
    
    try:
        server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
        print("[HTTP] Servidor iniciado en puerto 80")
        while True:
            await asyncio.sleep(3600)
    except Exception as e:
        print("[ERROR] No se pudo iniciar el servidor: {}".format(e))

# Inicialización limpia de la tarea principal
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\n[INFO] Servidor web detenido correctamente.")
