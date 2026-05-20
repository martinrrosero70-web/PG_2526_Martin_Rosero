# ============================================================
#  GRUA TORRE - main.py  (ESP32 MicroPython)
# ============================================================
#  Servidor web asincrono (uasyncio) + UART hacia Arduino Nano
#  Puerto UART TX: GPIO 17  @  9600 bps
#
#  Endpoints HTTP:
#    GET  /          -> HTML del panel de control
#    POST /cmd?c=X   -> Enviar comando X por UART (F/B/U/D/L/R/S)
#    GET  /status    -> JSON { "ip": "...", "last_cmd": "X" }
#    GET  /telemetry -> JSON de telemetría del sistema
# ============================================================

import uasyncio as asyncio
import network
import ujson
from machine import UART, Pin
import time

# ── UART hacia Arduino Nano ──────────────────────────────────
uart = UART(2, baudrate=9600, tx=17, rx=16)

# ── LED de estado ────────────────────────────────────────────
led = Pin(2, Pin.OUT)

# ── Estado global ────────────────────────────────────────────
last_cmd = "S"
telemetry = {
  "start_ms": time.ticks_ms(),
  "commands": {"F": 0, "B": 0, "U": 0, "D": 0, "L": 0, "R": 0, "S": 0},
  "http_requests": 0,
  "http_errors": 0,
  "last_error": None,
}

# ── HTML del panel de control (cadena Python) ────────────────
HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Control Grua Torre</title>
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #21262d;
    --accent: #f78166;
    --accent2: #79c0ff;
    --text: #e6edf3;
    --muted: #8b949e;
    --radius: 16px;
    --btn-size: 80px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 16px;
  }
  header {
    text-align: center;
    margin-bottom: 28px;
  }
  header h1 {
    font-size: 1.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  header p { color: var(--muted); font-size: 0.85rem; margin-top: 4px; }
  .status-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--surface2);
    border: 1px solid #30363d;
    border-radius: 50px;
    padding: 6px 16px;
    font-size: 0.8rem;
    color: var(--muted);
    margin-bottom: 32px;
  }
  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #3fb950;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%,100% { opacity: 1; }
    50%      { opacity: 0.4; }
  }
  .panels {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    width: 100%;
    max-width: 600px;
  }
  .panel {
    background: var(--surface);
    border: 1px solid #30363d;
    border-radius: var(--radius);
    padding: 20px;
  }
  .panel h2 {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    margin-bottom: 16px;
    text-align: center;
  }
  .dpad {
    display: grid;
    grid-template-columns: repeat(3, var(--btn-size));
    grid-template-rows:  repeat(3, var(--btn-size));
    gap: 6px;
    justify-content: center;
  }
  .dpad .empty { visibility: hidden; }
  .btn {
    width: var(--btn-size);
    height: var(--btn-size);
    border: none;
    border-radius: 14px;
    font-size: 1.6rem;
    cursor: pointer;
    background: var(--surface2);
    color: var(--text);
    transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
    user-select: none;
    -webkit-user-select: none;
    touch-action: manipulation;
  }
  .btn:hover  { background: #2d333b; }
  .btn:active,
  .btn.active { background: var(--accent); transform: scale(0.93); box-shadow: 0 0 18px rgba(247,129,102,.45); }
  .btn.stop {
    background: #6e40c9;
    grid-column: 2; grid-row: 2;
  }
  .btn.stop:active { background: #9a6cf0; box-shadow: 0 0 18px rgba(110,64,201,.5); }
  .rotation-panel { grid-column: span 2; }
  .rot-row {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-top: 8px;
  }
  .btn-wide {
    width: 140px;
    height: 64px;
    font-size: 1.3rem;
    border-radius: 14px;
  }
  .last-cmd-box {
    margin-top: 28px;
    background: var(--surface);
    border: 1px solid #30363d;
    border-radius: var(--radius);
    padding: 14px 20px;
    width: 100%;
    max-width: 600px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .last-cmd-box span { color: var(--muted); font-size: 0.85rem; }
  #lastCmd {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--accent2);
    letter-spacing: 0.05em;
  }
  .telemetry-box {
    margin-top: 18px;
    background: var(--surface);
    border: 1px solid #30363d;
    border-radius: var(--radius);
    padding: 18px 20px;
    width: 100%;
    max-width: 600px;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    color: var(--text);
  }
  .telemetry-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 0.9rem;
  }
  .telemetry-item span:last-child {
    color: var(--accent2);
    font-weight: 700;
    font-size: 1.1rem;
  }
  @media (max-width: 400px) {
    :root { --btn-size: 68px; }
    .panels { grid-template-columns: 1fr; }
    .rotation-panel { grid-column: 1; }
  }
</style>
</head>
<body>

<header>
  <h1>&#x1F3D7; Grua Torre</h1>
  <p>Control Remoto &mdash; ESP32 MicroPython</p>
</header>

<div class="status-bar">
  <div class="dot"></div>
  <span id="connStatus">Conectado al ESP32</span>
</div>

<div class="panels">

  <!-- Panel Carro (horizontal) -->
  <div class="panel">
    <h2>&#x1F69B; Carro</h2>
    <div class="dpad">
      <div class="empty"></div>
      <button class="btn" id="btnF" data-cmd="F">&#x25B2;</button>
      <div class="empty"></div>
      <div class="empty"></div>
      <button class="btn stop" id="btnS" data-cmd="S">&#x23F9;</button>
      <div class="empty"></div>
      <div class="empty"></div>
      <button class="btn" id="btnB" data-cmd="B">&#x25BC;</button>
      <div class="empty"></div>
    </div>
  </div>

  <!-- Panel Elevacion -->
  <div class="panel">
    <h2>&#x1F4E6; Elevacion</h2>
    <div class="dpad">
      <div class="empty"></div>
      <button class="btn" id="btnU" data-cmd="U">&#x2B06;</button>
      <div class="empty"></div>
      <div class="empty"></div>
      <div class="empty"></div>
      <div class="empty"></div>
      <div class="empty"></div>
      <button class="btn" id="btnD" data-cmd="D">&#x2B07;</button>
      <div class="empty"></div>
    </div>
  </div>

  <!-- Panel Rotacion -->
  <div class="panel rotation-panel">
    <h2>&#x1F504; Rotacion (Nema 17)</h2>
    <div class="rot-row">
      <button class="btn btn-wide" id="btnL" data-cmd="L">&#x21A9; Izq</button>
      <button class="btn btn-wide" id="btnR" data-cmd="R">Der &#x21AA;</button>
    </div>
  </div>

</div>

<div class="last-cmd-box">
  <span>Ultimo comando enviado:</span>
  <span id="lastCmd">--</span>
</div>
<div class="telemetry-box">
  <div class="telemetry-item">
    <span>Uptime</span>
    <span id="uptime">--</span>
  </div>
  <div class="telemetry-item">
    <span>Comandos totales</span>
    <span id="cmdCount">--</span>
  </div>
  <div class="telemetry-item">
    <span>Solicitudes HTTP</span>
    <span id="httpRequests">--</span>
  </div>
  <div class="telemetry-item">
    <span>Errores HTTP</span>
    <span id="httpErrors">--</span>
  </div>
  <div class="telemetry-item">
    <span>LED estado</span>
    <span id="ledState">--</span>
  </div>
  <div class="telemetry-item">
    <span>IP actual</span>
    <span id="ipAddr">--</span>
  </div>
</div>

<script>
(function(){
  const HOLD_INTERVAL = 200;   // ms entre envios al mantener presionado
  const CMD_MAP = {
    'F':'Carro Adelante','B':'Carro Atras',
    'U':'Subir','D':'Bajar',
    'L':'Giro Izq','R':'Giro Der','S':'Stop'
  };
  let holdTimer = null;
  let activeBtn = null;

  async function sendCmd(cmd){
    try {
      const r = await fetch('/cmd?c=' + cmd, {method:'POST'});
      if(r.ok){
        document.getElementById('lastCmd').textContent =
          cmd + ' \u2014 ' + (CMD_MAP[cmd] || cmd);
        updateTelemetry();
      }
    } catch(e){
      document.getElementById('connStatus').textContent = 'Error de conexion';
    }
  }

  function startHold(btn){
    const cmd = btn.dataset.cmd;
    btn.classList.add('active');
    activeBtn = btn;
    sendCmd(cmd);
    holdTimer = setInterval(() => sendCmd(cmd), HOLD_INTERVAL);
  }

  function stopHold(){
    if(holdTimer){ clearInterval(holdTimer); holdTimer = null; }
    if(activeBtn){ activeBtn.classList.remove('active'); activeBtn = null; }
    sendCmd('S');
  }

  document.querySelectorAll('.btn').forEach(btn => {
    const isStop = btn.dataset.cmd === 'S';

    btn.addEventListener('mousedown',  e => { e.preventDefault(); isStop ? sendCmd('S') : startHold(btn); });
    btn.addEventListener('touchstart', e => { e.preventDefault(); isStop ? sendCmd('S') : startHold(btn); }, {passive:false});

    if(!isStop){
      ['mouseup','mouseleave','touchend','touchcancel'].forEach(ev =>
        btn.addEventListener(ev, e => { e.preventDefault(); stopHold(); })
      );
    }
  });
  async function updateTelemetry(){
    try {
      const r = await fetch('/telemetry');
      if(!r.ok) return;
      const t = await r.json();
      document.getElementById('uptime').textContent = t.uptime_s + ' s';
      document.getElementById('cmdCount').textContent = Object.values(t.commands).reduce((a,b) => a + b, 0);
      document.getElementById('httpRequests').textContent = t.http_requests;
      document.getElementById('httpErrors').textContent = t.http_errors;
      document.getElementById('ledState').textContent = t.led;
      document.getElementById('ipAddr').textContent = t.ip;
    } catch (e) {
      // Ignorar errores de telemetría de UI
    }
  }
  updateTelemetry();
  setInterval(updateTelemetry, 4000);
})();
</script>
</body>
</html>
"""

# ── Helper: parsear ruta y query de la solicitud HTTP ────────
def parse_request(request_line):
    """Devuelve (metodo, path, query_string)."""
    try:
        parts = request_line.split(" ")
        method = parts[0]
        full_path = parts[1] if len(parts) > 1 else "/"
        if "?" in full_path:
            path, qs = full_path.split("?", 1)
        else:
            path, qs = full_path, ""
        return method, path, qs
    except Exception:
        return "GET", "/", ""

def get_query_param(qs, key):
    """Extrae valor de un parametro en la query string."""
    for pair in qs.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            if k == key:
                return v
    return None

def get_local_ip():
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        return wlan.ifconfig()[0]
    return "0.0.0.0"

def get_uptime_seconds():
  return time.ticks_diff(time.ticks_ms(), telemetry["start_ms"]) // 1000

# ── Manejador de conexiones HTTP ─────────────────────────────
async def handle_client(reader, writer):
    global last_cmd
    telemetry["http_requests"] += 1
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=3)
        request_line = request_line.decode("utf-8", "ignore").strip()

        # Consumir cabeceras restantes
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=2)
            if line in (b"\r\n", b"\n", b""):
                break

        method, path, qs = parse_request(request_line)

        # ── GET / ── Panel de control HTML ───────────────────
        if path == "/" and method == "GET":
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n" + HTML
            writer.write(response.encode())

        # ── POST /cmd?c=X ── Enviar comando UART ─────────────
        elif path == "/cmd" and method == "POST":
          cmd = get_query_param(qs, "c")
          valid = ("F", "B", "U", "D", "L", "R", "S")
          if cmd and cmd in valid:
            uart.write(cmd)
            last_cmd = cmd
            telemetry["commands"][cmd] += 1
            led.on() if cmd != "S" else led.off()
            body = ujson.dumps({"ok": True, "cmd": cmd})
          else:
            body = ujson.dumps({"ok": False, "error": "invalid cmd"})
          # ✅ CORRECCIÓN: la respuesta se construye FUERA del if/else
          #    para que se envíe siempre (tanto cmd válido como inválido)
          response = ("HTTP/1.1 200 OK\r\n"
                      "Content-Type: application/json\r\n"
                      "Connection: close\r\n\r\n" + body)
          writer.write(response.encode())

        # ── GET /status ── JSON de estado ────────────────────
        elif path == "/status" and method == "GET":
            body = ujson.dumps({"ip": get_local_ip(), "last_cmd": last_cmd})
            response = ("HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/json\r\n"
                        "Connection: close\r\n\r\n" + body)
            writer.write(response.encode())

        # ── GET /telemetry ── JSON de telemetría del sistema ───────
        elif path == "/telemetry" and method == "GET":
          body = ujson.dumps({
            "ip": get_local_ip(),
            "last_cmd": last_cmd,
            "uptime_s": get_uptime_seconds(),
            "commands": telemetry["commands"],
            "http_requests": telemetry["http_requests"],
            "http_errors": telemetry["http_errors"],
            "last_error": telemetry["last_error"],
            "led": "on" if led.value() else "off",
          })
          response = ("HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                "Connection: close\r\n\r\n" + body)
          writer.write(response.encode())

        # ── 404 ──────────────────────────────────────────────
        else:
            writer.write(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")

        await writer.drain()
    except Exception as e:
        telemetry["http_errors"] += 1
        telemetry["last_error"] = str(e)
        print("[HTTP] Error:", e)
    finally:
        writer.close()
        await writer.wait_closed()

# ── Main asincrono ────────────────────────────────────────────
async def main():
    ip = get_local_ip()
    print("=" * 45)
    print("  GRUA TORRE - Servidor Web ESP32")
    print("  IP:", ip)
    print("  URL: http://{}".format(ip))
    print("=" * 45)

    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("[Server] Escuchando en puerto 80 ...")
    async with server:
        await server.serve_forever()

# ── Punto de entrada ──────────────────────────────────────────
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("[Server] Detenido por usuario.")
