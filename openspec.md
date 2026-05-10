# OpenSpec — Grúa Torre Controlada Remotamente
## Versión: 1.0 | Fecha: 2026-05-10 | Estado: Draft

---

## 1. Resumen del Sistema

| Campo | Valor |
|---|---|
| Nombre del sistema | Grúa Torre – Control Dual |
| Versión de firmware | Arduino: v2.0 · ESP32: v1.0 |
| Autor | Martín Rosero |
| Repositorio GitHub | [PG_2526_Martin_Rosero](https://github.com/martinrrosero70/PG_2526_Martin_Rosero) |

### 1.1 Descripción funcional

Sistema embebido de dos controladores para una grúa torre con **tres grados de libertad** (carro horizontal, elevación vertical, rotación del eje principal) mediante:

- **Control manual** — Tres joysticks analógicos conectados al Arduino Nano.
- **Control remoto** — Interfaz web servida por el ESP32, accesible desde cualquier navegador en la misma red WiFi.

Ambos canales de control se **suman** en el Arduino Nano (control mixto).

---

## 2. Arquitectura de Hardware

```
[ Navegador / Móvil ]
         │  HTTP / port 80
         ▼
[ ESP32 DevKit V1 — MicroPython ]
         │  UART 9600 bps (GPIO 17 TX → Arduino D0 RX)
         ▼
[ Arduino Nano ]
  ├── TB6612FNG → Motor A (Carro)
  ├── TB6612FNG → Motor B (Elevación)
  └── DRV8825   → Nema 17 (Rotación)
        ▲
  [Joy A0] [Joy A1] [Joy A2]
```

### 2.1 Pines — Arduino Nano

| Función | Pin | Tipo |
|---|---|---|
| Joystick Carro (X) | A0 | Entrada analógica |
| Joystick Elevación (Y) | A1 | Entrada analógica |
| Joystick Giro (Z) | A2 | Entrada analógica |
| TB6612 AIN1 (Carro dir+) | D2 | Salida digital |
| TB6612 PWMA (Carro vel) | D3 | Salida PWM |
| TB6612 AIN2 (Carro dir-) | D4 | Salida digital |
| TB6612 PWMB (Elevación vel) | D5 | Salida PWM |
| TB6612 BIN1 (Elevación dir+) | D7 | Salida digital |
| TB6612 BIN2 (Elevación dir-) | D8 | Salida digital |
| DRV8825 STEP | D9 | Salida digital |
| DRV8825 DIR | D10 | Salida digital |
| UART RX (desde ESP32 TX) | D0 | UART hardware |

### 2.2 Pines — ESP32 DevKit V1

| Función | Pin | Tipo |
|---|---|---|
| UART TX (hacia Arduino D0) | GPIO 17 | UART hardware |
| UART RX (no usado) | GPIO 16 | UART hardware |
| LED de estado | GPIO 2 | Salida digital |

---

## 3. Protocolo UART

### 3.1 Parámetros de enlace

| Parámetro | Valor |
|---|---|
| Baudrate | 9600 bps |
| Bits de datos | 8 |
| Paridad | Ninguna |
| Bits de stop | 1 |
| Control de flujo | Ninguno |
| Dirección | ESP32 TX → Arduino Nano RX |

### 3.2 Comandos (1 byte por mensaje)

| Byte | Hex | Acción |
|---|---|---|
| `F` | 0x46 | Carro adelante |
| `B` | 0x42 | Carro atrás |
| `U` | 0x55 | Elevación sube |
| `D` | 0x44 | Elevación baja |
| `L` | 0x4C | Rotación izquierda |
| `R` | 0x52 | Rotación derecha |
| `S` | 0x53 | Stop (todos los actuadores) |

### 3.3 Timeout de seguridad

```
Si (millis() - lastWebCmd) > 500 ms:
    webCarroDir = webElevDir = webGiroDir = 0
```

El cliente web reenvía el comando cada 200 ms mientras el botón está presionado. Al soltar envía `S`. El timeout de 500 ms actúa como red de seguridad ante pérdida de red.

### 3.4 Diagrama de secuencia

```
Navegador        ESP32            Arduino Nano
   │──POST /cmd?c=F──►│               │
   │                   │──UART "F"────►│
   │◄──200 {ok:true}───│               │  (Motor avanza)
   │  [200ms después]  │               │
   │──POST /cmd?c=F──►│               │
   │                   │──UART "F"────►│
   │──POST /cmd?c=S──►│  (al soltar)  │
   │                   │──UART "S"────►│  (Motor para)
```

---

## 4. API REST del Servidor Web

**Base URL:** `http://<IP_ESP32>` (puerto 80)

---

### 4.1 `GET /`

Entrega la interfaz de control HTML completa.

**Response:** `200 OK` · `Content-Type: text/html`

---

### 4.2 `POST /cmd`

Envía un comando de movimiento al Arduino vía UART.

**Query param:** `c` (string, 1 char) — Valores: `F B U D L R S`

**Response exitosa:**
```json
{ "ok": true, "cmd": "F" }
```

**Response de error:**
```json
{ "ok": false, "error": "invalid cmd" }
```

> [!NOTE]
> El código HTTP siempre es 200. El resultado real se indica en el campo `ok`.

---

### 4.3 `GET /status`

Estado actual del servidor.

**Response:**
```json
{ "ip": "192.168.1.105", "last_cmd": "S" }
```

| Campo | Tipo | Descripción |
|---|---|---|
| `ip` | string | IP actual del ESP32 |
| `last_cmd` | string | Último comando UART enviado |

---

## 5. Lógica de Control Mixto

```
finalCarroSpeed = constrain(joyCarroSpeed + webCarroDir × 220, −220, +220)
finalElevSpeed  = constrain(joyElevSpeed  + webElevDir  × 220, −220, +220)
finalGiroDir    = constrain(joyGiroDir    + webGiroDir,          −1,   +1)
```

| Variable | Rango | Descripción |
|---|---|---|
| `joyCarroSpeed` | −220 … +220 | PWM desde joystick (zona muerta ±50 ADC) |
| `webCarroDir` | −1, 0, +1 | Intención direccional desde la web |

---

## 6. Parámetros Stepper (Nema 17 + DRV8825)

| Parámetro | Valor | Unidad |
|---|---|---|
| Velocidad máxima | 800 | pasos/seg |
| Aceleración | 400 | pasos/seg² |
| Velocidad modo web | 300 | pasos/seg |
| Modo de control | AccelStepper::DRIVER | — |

---

## 7. Dependencias de Software

### Arduino Nano
| Librería | Versión mínima | Fuente |
|---|---|---|
| AccelStepper | 1.64 | Arduino Library Manager |

### ESP32 MicroPython
| Módulo | Incluido | Notas |
|---|---|---|
| `uasyncio` | Sí (≥ 1.19) | Servidor web asíncrono |
| `ujson` | Sí | Serialización JSON |
| `network` | Sí | Gestión WiFi |
| `machine.UART` | Sí | Comunicación serial |

---

## 8. Guía de Despliegue

### Arduino Nano
1. Instalar **AccelStepper** desde Library Manager.
2. Abrir `grua_arduino.ino` · Placa: `Arduino Nano` · Procesador: `ATmega328P (Old Bootloader)`.
3. Verificar y subir el sketch.

### ESP32
1. Flashear MicroPython (≥ 1.22) con `esptool`.
2. Editar `WIFI_SSID` y `WIFI_PASSWORD` en `boot.py`.
3. Subir `boot.py` y `main.py` con **Thonny IDE**.
4. Reiniciar el ESP32; la IP aparece en la consola serial.
5. Abrir esa IP en un navegador del mismo router.

### Conexión UART
```
ESP32 GPIO 17 (TX) ──────► Arduino Nano D0 (RX)
ESP32 GND           ──────► Arduino Nano GND
```

> [!WARNING]
> El ESP32 opera a 3.3 V y el Nano a 5 V. Para mayor seguridad, usar un divisor resistivo (1 kΩ / 2 kΩ) en la línea TX→RX.

---

## 9. Glosario

| Término | Definición |
|---|---|
| Carro | Carruaje horizontal sobre la pluma de la grúa |
| Elevación | Mecanismo vertical de subida/bajada del gancho |
| Giro / Rotación | Movimiento angular del conjunto superior (360°) |
| TB6612FNG | Driver dual de puente H para motores DC |
| DRV8825 | Driver de microstepping para motores a pasos (hasta 1/32) |
| Nema 17 | Estándar de motor a pasos (42 mm × 42 mm) |
| AccelStepper | Librería Arduino para control no bloqueante de steppers |
| uasyncio | Implementación de asyncio para MicroPython |
| Control mixto | Suma de intenciones de dos fuentes de control |
| Timeout de seguridad | Detiene actuadores si no llega comando en N ms |
