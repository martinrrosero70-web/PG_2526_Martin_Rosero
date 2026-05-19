import network
import asyncio
import time
import machine

# Configuración de tu red
WIFI_SSID = 'Cudy-0138'
WIFI_PASS = '41659458'  # Asegúrate de poner tu contraseña real aquí

def conectar_wifi():
    """Conecta al WiFi previniendo el error de estado interno."""
    wlan = network.WLAN(network.STA_IF)
    
    # 1. FORZAR RESET DEL ESTADO INTERNO DEL WIFI
    print("[WiFi] Limpiando estado previo de la radio...")
    wlan.active(False)  # Desactivar por completo
    time.sleep(1)       # Pausa física para que el chip se apague
    
    # 2. ACTIVAR E INICIAR CONEXIÓN
    wlan.active(True)   # Volver a activar de forma limpia
    
    if not wlan.isconnected():
        print(f"[WiFi] Conectando a '{WIFI_SSID}' ...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        
        # Contador de intentos para evitar bucles infinitos si la clave está mal
        intentos = 0
        while not wlan.isconnected() and intentos < 20:
            time.sleep(0.5)
            intentos += 1
            
    if wlan.isconnected():
        print('=============================================')
        print('  GRUA TORRE - Servidor Web ESP32')
        print('  IP:', wlan.ifconfig()[0])
        print('  URL: http://' + wlan.ifconfig()[0])
        print('=============================================')
    else:
        print("[WiFi] Error: No se pudo conectar. Verifica SSID/Contraseña.")
        # Si sigue fallando de forma interna, forzamos un reinicio físico (Hard Reset)
        print("[WiFi] Reiniciando placa para solucionar error de hardware...")
        time.sleep(2)
        machine.reset() 

async def handle_client(reader, writer):
    # (Mantén aquí tu lógica de handle_client idéntica a como la tenías)
    try:
        request_line = await reader.readline()
        # ... resto de tu código de control de la grúa e HTML ...
        html = "HTTP/1.1 200 OK\r\n\r\n<h1>Grua Torre Ok</h1>"
        writer.write(html.encode('utf-8'))
        await writer.drain()
    except Exception as e:
        print("Error:", e)
    finally:
        await writer.close()

async def main():
    """Función principal corregida para MicroPython."""
    server = await asyncio.start_server(handle_client, '0.0.0.0', 80)
    print("[Server] Escuchando en puerto 80 ...")
    
    # Mantiene el servidor vivo sin usar serve_forever()
    while True:
        await asyncio.sleep(3600)

# --- FLUJO DE EJECUCIÓN ---

# Ejecutamos la conexión limpia
conectar_wifi()

# Arrancamos el loop asíncrono
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nServidor detenido manualmente.")