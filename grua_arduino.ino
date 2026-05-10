/*
 * ============================================================
 *  GRÚA TORRE - Firmware Arduino Nano v2.0
 * ============================================================
 *  Controlador A: Arduino Nano
 *  Descripción : Controla dos motores DC (N20) via TB6612FNG
 *                y un motor a pasos NEMA 17 via DRV8825.
 *                Lee joysticks analógicos y comandos Serial
 *                del ESP32. La intención del joystick y la
 *                del comando web se SUMAN para el control mixto.
 *
 *  Pines:
 *    Joystick Carro     -> A0
 *    Joystick Elevación -> A1
 *    Joystick Giro      -> A2
 *
 *    TB6612FNG Motor A (Carro):
 *      AIN1 -> D2,  AIN2 -> D4,  PWMA -> D3
 *    TB6612FNG Motor B (Elevación):
 *      BIN1 -> D7,  BIN2 -> D8,  PWMB -> D5
 *    STBY   -> VCC (5 V, jumper permanente)
 *
 *    DRV8825 (Nema 17 - Eje de Rotación):
 *      STEP -> D9,  DIR -> D10
 *
 *    Serial (RX D0) <- TX del ESP32 @ 9600 bps
 *
 *  Protocolo de comandos Serial (1 byte):
 *    'F' = Carro Adelante    'B' = Carro Atrás
 *    'U' = Elevación Subir   'D' = Elevación Bajar
 *    'L' = Giro Izquierda    'R' = Giro Derecha
 *    'S' = Stop (todos los actuadores)
 *
 *  Dependencias:
 *    - AccelStepper (v1.64+): instalar desde Library Manager
 * ============================================================
 */

#include <AccelStepper.h>

// ── Pines TB6612FNG Motor A – Carro ────────────────────────
#define AIN1 2
#define AIN2 4
#define PWMA 3

// ── Pines TB6612FNG Motor B – Elevación ────────────────────
#define BIN1 7
#define BIN2 8
#define PWMB 5

// ── Pines DRV8825 – Nema 17 Rotación ───────────────────────
#define STEP_PIN 9
#define DIR_PIN  10

// ── Pines Joysticks ─────────────────────────────────────────
#define JOY_CARRO    A0
#define JOY_ELEVACION A1
#define JOY_GIRO     A2

// ── Parámetros de movimiento ────────────────────────────────
#define DEADZONE          50      // zona muerta joystick (0-511 centro)
#define JOY_CENTER        512     // valor neutro ADC
#define MAX_PWM           220     // velocidad máxima motores DC
#define STEPPER_MAX_SPEED 800.0f  // pasos/seg máximo Nema 17
#define STEPPER_ACCEL     400.0f  // aceleración pasos/seg²
#define WEB_STEPPER_SPEED 300.0f  // velocidad modo remoto
#define WEB_TIMEOUT_MS    500     // ms sin comando → detener actuadores web

// ── AccelStepper – modo STEP/DIR (driver externo) ──────────
AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

// ── Variables de intención web ──────────────────────────────
int  webCarroDir    = 0;   // -1, 0, +1
int  webElevDir     = 0;
int  webGiroDir     = 0;
unsigned long lastWebCmd = 0;  // timestamp último comando serial

// ─────────────────────────────────────────────────────────────
//  PROTOTIPOS
// ─────────────────────────────────────────────────────────────
void driveMotorA(int speed);   // Carro     (+ adelante, - atrás)
void driveMotorB(int speed);   // Elevación (+ subir,    - bajar)
void parseSerial();
int  joyToSpeed(int rawADC);

// ─────────────────────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
  // Serial hacia ESP32 (también para debug si se conecta al PC)
  Serial.begin(9600);

  // Pines TB6612FNG
  pinMode(AIN1, OUTPUT); pinMode(AIN2, OUTPUT); pinMode(PWMA, OUTPUT);
  pinMode(BIN1, OUTPUT); pinMode(BIN2, OUTPUT); pinMode(PWMB, OUTPUT);

  // Apagar ambos motores al arrancar
  driveMotorA(0);
  driveMotorB(0);

  // Configurar AccelStepper
  stepper.setMaxSpeed(STEPPER_MAX_SPEED);
  stepper.setAcceleration(STEPPER_ACCEL);
  stepper.setCurrentPosition(0);
}

// ─────────────────────────────────────────────────────────────
//  LOOP PRINCIPAL
// ─────────────────────────────────────────────────────────────
void loop() {
  // 1. Leer y decodificar comandos Serial del ESP32
  parseSerial();

  // 2. Timeout de seguridad: si no llega comando web → reset intención web
  if (millis() - lastWebCmd > WEB_TIMEOUT_MS) {
    webCarroDir = 0;
    webElevDir  = 0;
    webGiroDir  = 0;
  }

  // 3. Leer joysticks → velocidades normalizadas
  int joyCarroSpeed    = joyToSpeed(analogRead(JOY_CARRO));
  int joyElevSpeed     = joyToSpeed(analogRead(JOY_ELEVACION));
  int joyGiroDir       = 0;
  int joyGiroRaw       = analogRead(JOY_GIRO) - JOY_CENTER;
  if      (joyGiroRaw >  DEADZONE) joyGiroDir = +1;
  else if (joyGiroRaw < -DEADZONE) joyGiroDir = -1;

  // 4. Control mixto (suma intención joystick + web)
  //    Se satura al rango válido para evitar over-drive.
  int finalCarroSpeed = constrain(joyCarroSpeed + webCarroDir * MAX_PWM, -MAX_PWM, MAX_PWM);
  int finalElevSpeed  = constrain(joyElevSpeed  + webElevDir  * MAX_PWM, -MAX_PWM, MAX_PWM);
  int finalGiroDir    = constrain(joyGiroDir    + webGiroDir,             -1,        1);

  // 5. Aplicar a motores DC
  driveMotorA(finalCarroSpeed);
  driveMotorB(finalElevSpeed);

  // 6. Control stepper (no bloqueante vía AccelStepper)
  if (finalGiroDir != 0) {
    // Genera un objetivo "lejano" en la dirección deseada para movimiento continuo
    long target = stepper.currentPosition() + (long)(finalGiroDir) * 100000L;
    stepper.moveTo(target);
    stepper.setMaxSpeed(STEPPER_MAX_SPEED);
  } else {
    // Detener suavemente
    stepper.stop();
  }
  stepper.run();  // debe llamarse en cada iteración del loop
}

// ─────────────────────────────────────────────────────────────
//  parseSerial() – Decodifica comandos de 1 byte del ESP32
// ─────────────────────────────────────────────────────────────
void parseSerial() {
  while (Serial.available() > 0) {
    char cmd = (char)Serial.read();
    lastWebCmd = millis();   // reset timeout al recibir cualquier byte válido

    switch (cmd) {
      case 'F': webCarroDir = +1; webElevDir = 0; webGiroDir = 0; break;
      case 'B': webCarroDir = -1; webElevDir = 0; webGiroDir = 0; break;
      case 'U': webElevDir  = +1; webCarroDir= 0; webGiroDir = 0; break;
      case 'D': webElevDir  = -1; webCarroDir= 0; webGiroDir = 0; break;
      case 'L': webGiroDir  = -1; webCarroDir= 0; webElevDir = 0; break;
      case 'R': webGiroDir  = +1; webCarroDir= 0; webElevDir = 0; break;
      case 'S':
        webCarroDir = 0;
        webElevDir  = 0;
        webGiroDir  = 0;
        driveMotorA(0);
        driveMotorB(0);
        stepper.stop();
        break;
      default: break;  // byte desconocido → ignorar
    }
  }
}

// ─────────────────────────────────────────────────────────────
//  joyToSpeed() – Mapea ADC (0-1023) a velocidad PWM con deadzone
// ─────────────────────────────────────────────────────────────
int joyToSpeed(int rawADC) {
  int centered = rawADC - JOY_CENTER;  // rango ~ -512 a +511
  if (abs(centered) < DEADZONE) return 0;
  // Mapear a rango -MAX_PWM .. +MAX_PWM
  return map(centered, -512, 511, -MAX_PWM, MAX_PWM);
}

// ─────────────────────────────────────────────────────────────
//  driveMotorA() – TB6612FNG Motor A (Carro)
//  speed: -MAX_PWM a +MAX_PWM  (negativo = sentido inverso)
// ─────────────────────────────────────────────────────────────
void driveMotorA(int speed) {
  speed = constrain(speed, -MAX_PWM, MAX_PWM);
  if (speed == 0) {
    digitalWrite(AIN1, LOW);
    digitalWrite(AIN2, LOW);
    analogWrite(PWMA, 0);
  } else if (speed > 0) {
    digitalWrite(AIN1, HIGH);
    digitalWrite(AIN2, LOW);
    analogWrite(PWMA, speed);
  } else {
    digitalWrite(AIN1, LOW);
    digitalWrite(AIN2, HIGH);
    analogWrite(PWMA, -speed);
  }
}

// ─────────────────────────────────────────────────────────────
//  driveMotorB() – TB6612FNG Motor B (Elevación)
//  speed: -MAX_PWM a +MAX_PWM  (positivo = subir)
// ─────────────────────────────────────────────────────────────
void driveMotorB(int speed) {
  speed = constrain(speed, -MAX_PWM, MAX_PWM);
  if (speed == 0) {
    digitalWrite(BIN1, LOW);
    digitalWrite(BIN2, LOW);
    analogWrite(PWMB, 0);
  } else if (speed > 0) {
    digitalWrite(BIN1, HIGH);
    digitalWrite(BIN2, LOW);
    analogWrite(PWMB, speed);
  } else {
    digitalWrite(BIN1, LOW);
    digitalWrite(BIN2, HIGH);
    analogWrite(PWMB, -speed);
  }
}
