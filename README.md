# 🏗️ Grúa Torre — Control Dual (Joystick + Web)

**Autor:** Martín Rosero  
**Repositorio:** `PG_2526_Martin_Rosero`  
**Fecha:** 2026-05-10  
**Versión:** 2.0

---

## 📋 Descripción General

Sistema embebido de **control dual** para una grúa torre funcional con tres grados de libertad:

| Eje | Actuador | Driver |
|---|---|---|
| Carro horizontal | Motor DC N20 (Motor A) | TB6612FNG |
| Elevación vertical | Motor DC N20 (Motor B) | TB6612FNG |
| Rotación principal | **Motor a pasos Nema 17** | **DRV8825** ✨ |

> **Mejora técnica clave:** El eje de rotación usa un motor **Nema 17** controlado por el driver **DRV8825**, logrando precisión milimétrica en el giro (microstepping 1/32) en lugar de un motor DC convencional.

El sistema permite **dos modos de control simultáneos**:
- 🕹️ **Manual** — Tres joysticks analógicos conectados al Arduino Nano
- 🌐 **Remoto** — Interfaz web servida por el ESP32 en MicroPython, accesible desde cualquier dispositivo en la red WiFi local

Ambas fuentes de control se **suman** (control mixto), permitiendo operar ambas a la vez.

---

## 🗂️ Estructura del Repositorio

```
PG_2526_Martin_Rosero/
├── grua_arduino.ino   # Firmware Arduino Nano (TB6612FNG + DRV8825 + joysticks)
├── boot.py            # ESP32 MicroPython — Conexión WiFi con reintentos
├── main.py            # ESP32 MicroPython — Servidor web asíncrono + UART
├── openspec.md        # Documentación técnica OpenSpec v1.0
└── README.md          # Este archivo
```

---

## 🔌 Diagrama de Arquitectura

```
[ Navegador / Móvil ]
         │  HTTP (puerto 80)
         ▼
[ ESP32 DevKit V1 — MicroPython ]
         │  UART 9600 bps
         │  GPIO 17 (TX) ──────────────────────────────────► D0 (RX)
         ▼
[ Arduino Nano ]
  ├── TB6612FNG ──► Motor A — Carro horizontal (N20)
  ├── TB6612FNG ──► Motor B — Elevación vertical (N20)
  └── DRV8825   ──► Nema 17 — Rotación del eje principal ⭐
         ▲
   [Joy A0] [Joy A1] [Joy A2]
```

---

## 🔧 Conexionado de Hardware

### Arduino Nano

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
| UART RX (desde ESP32) | D0 | UART hardware |

### ESP32 DevKit V1

| Función | Pin | Tipo |
|---|---|---|
| UART TX (hacia Arduino D0) | GPIO 17 | UART hardware |
| UART RX (no usado) | GPIO 16 | UART hardware |
| LED de estado WiFi | GPIO 2 | Salida digital |

> ⚠️ **Importante:** El ESP32 trabaja a 3.3 V y el Arduino Nano a 5 V. Para proteger el ESP32, usar un divisor resistivo (1 kΩ + 2 kΩ) en la línea TX→RX, o un level shifter.

---

## 📡 Protocolo UART

| Byte | Hex | Acción |
|---|---|---|
| `F` | 0x46 | Carro adelante |
| `B` | 0x42 | Carro atrás |
| `U` | 0x55 | Elevación sube |
| `D` | 0x44 | Elevación baja |
| `L` | 0x4C | Rotación izquierda |
| `R` | 0x52 | Rotación derecha |
| `S` | 0x53 | Stop (todos los actuadores) |

**Baudrate:** 9600 bps · 8N1 · sin control de flujo  
**Timeout de seguridad:** Si no llega comando en **500 ms**, el Arduino para los actuadores web.

---

## 🌐 API REST del Servidor Web

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Panel HTML de control remoto |
| `/cmd?c=X` | POST | Envía comando X por UART al Arduino |
| `/status` | GET | Estado JSON: `{ "ip": "...", "last_cmd": "X" }` |

---

## ⚙️ Instalación y Despliegue

### Arduino Nano

1. Instalar librería **AccelStepper ≥ 1.64** desde el Library Manager del Arduino IDE.
2. Abrir `grua_arduino.ino`.
3. Configurar: Placa = `Arduino Nano` | Procesador = `ATmega328P (Old Bootloader)`.
4. Verificar → Subir.

### ESP32 MicroPython

1. Flashear MicroPython **≥ 1.22** con `esptool`:
   ```bash
   esptool.py --chip esp32 --port COMx erase_flash
   esptool.py --chip esp32 --port COMx write_flash -z 0x1000 esp32-micropython.bin
   ```
2. Editar `boot.py`: cambiar `TU_RED_WIFI` y `TU_CONTRASENA`.
3. Subir `boot.py` → `main.py` con **Thonny IDE**.
4. Reiniciar el ESP32. La IP aparece en la consola serial.
5. Abrir esa IP en el navegador del mismo router.

---

## 🎯 Parámetros del Motor a Pasos (Nema 17 + DRV8825)

| Parámetro | Valor |
|---|---|
| Velocidad máxima | 800 pasos/seg |
| Aceleración | 400 pasos/seg² |
| Velocidad modo web | 300 pasos/seg |
| Modo de microstepping | Configurable en DRV8825 (hasta 1/32) |
| Modo AccelStepper | `DRIVER` (STEP/DIR) |

---

## 📚 Documentación Técnica

Ver [`openspec.md`](./openspec.md) para la especificación técnica completa según el estándar **OpenSpec v1.0**, que incluye:
- Arquitectura de hardware detallada
- Protocolo UART completo con diagrama de secuencia
- API REST documentada
- Lógica de control mixto
- Guía de despliegue

---

## 🧰 Dependencias

| Componente | Dependencia | Versión |
|---|---|---|
| Arduino Nano | AccelStepper | ≥ 1.64 |
| ESP32 | MicroPython | ≥ 1.22 |
| ESP32 | `uasyncio` | Incluido en MicroPython |
| ESP32 | `ujson` | Incluido en MicroPython |

---

*Proyecto académico — Programación Gráfica 2025-2026 — Martín Rosero*
