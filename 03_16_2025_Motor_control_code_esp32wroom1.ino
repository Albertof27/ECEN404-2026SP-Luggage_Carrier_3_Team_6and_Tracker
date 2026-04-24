/********************************************************************
  Dual 24V Motor Controller
  Driver: BTN8982TA (two half-bridges per motor)
  MCU: ESP32-S3
  Core: ESP32 Arduino Core 3.x
********************************************************************/

// ================= PWM CONFIG =================
#define PWM_FREQ        10000 // was 20000
#define PWM_RESOLUTION  10
#define PWM_MAX         1023

// ================= CURRENT SENSE CONFIG =================
#define RIS_VALUE       1000.0
#define DK_IL_IS        19500.0
#define ADC_REF         3.3
#define ADC_MAX         4095.0

class Motor
{
  public: 

    Motor(int inhA, int inA, int isA,
          int inhB, int inB, int isB)
    {
      _inhA = inhA; _inA = inA; _isA = isA;
      _inhB = inhB; _inB = inB; _isB = isB;
    }

    void begin()
    {
      pinMode(_inhA, OUTPUT);
      pinMode(_inhB, OUTPUT);

      digitalWrite(_inhA, HIGH);
      digitalWrite(_inhB, HIGH);

      analogSetPinAttenuation(_isA, ADC_11db);
      analogSetPinAttenuation(_isB, ADC_11db);

      ledcAttach(_inA, PWM_FREQ, PWM_RESOLUTION);
      ledcAttach(_inB, PWM_FREQ, PWM_RESOLUTION);

      calibrateOffset();
    }

    void setCurrentLimit(float amps)
    {
      _currentLimit = amps;
    }

    void forward(uint16_t duty)
    { /*z */ 
      _targetDuty = constrain(duty, 0, PWM_MAX);
      _direction = 1;

       ledcWrite(_inB, 0);
    }

    void reverse(uint16_t duty)
    {
      _targetDuty = constrain(duty, 0, PWM_MAX);
      _direction = -1;

      ledcWrite(_inA, 0);
      ledcWrite(_inB, _targetDuty);
    }

    void brake()
    {
      _direction = 0;
      ledcWrite(_inA, PWM_MAX);
      ledcWrite(_inB, PWM_MAX);
    }

    void coast()
    {
      _direction = 0;
      ledcWrite(_inA, 0);
      ledcWrite(_inB, 0);
    }

    float readCurrent()
    {
      int adcValue = 0;

      if (_direction == 1)
        adcValue = analogRead(_isA);
      else if (_direction == -1)
        adcValue = analogRead(_isB);
      else
        return 0;

      float voltage = (adcValue / ADC_MAX) * ADC_REF;
      float IIS = voltage / RIS_VALUE;
      float IL = DK_IL_IS * (IIS - _offsetCurrent);

      return (IL > 0.0f) ? IL : 0.0f;
    }

    void updateCurrentControl()
    {
      float current = readCurrent();

      if (current > _currentLimit)
      {
        _targetDuty = max(0, _targetDuty - 5);
        applyDuty();
      }
    }

  private:

    int _inhA, _inA, _isA;
    int _inhB, _inB, _isB;

    float _offsetCurrent = 0;
    float _currentLimit = 15.0;
    int   _targetDuty = 0;
    int   _direction = 0;

    void applyDuty()
    {
      if (_direction == 1)
      {
        ledcWrite(_inA, _targetDuty);
        ledcWrite(_inB, 0);
      }
      else if (_direction == -1)
      {
        ledcWrite(_inA, 0);
        ledcWrite(_inB, _targetDuty);
      }
    }

    void calibrateOffset()
    {
      delay(200);

      long sum = 0;

      for (int i = 0; i < 200; i++)
      {
        sum += analogRead(_isA);
        delay(2);
      }

      float avg = sum / 200.0;
      float voltage = (avg / ADC_MAX) * ADC_REF;

      _offsetCurrent = voltage / RIS_VALUE;
    }
};

// ================= PIN DEFINITIONS ======================

// Motor 1
Motor motor1(
  21, 48, 35,
  47, 38, 36
);

// Motor 2
Motor motor2(
  8, 9, 3,
  10, 11, 4
);

// ================= SERIAL INPUT BUFFER ==================

String serialLine = "";
unsigned long lastCommandTime = 0;
const unsigned long COMMAND_TIMEOUT_MS = 500;

// ================= SETUP ================================

void setup()
{
  Serial.begin(115200);

  motor1.begin();
  motor2.begin();

  motor1.setCurrentLimit(12.0);
  motor2.setCurrentLimit(12.0);

  serialLine.reserve(64);

  motor1.coast();
  motor2.coast();

  Serial.println("ESP32 motor controller ready");
}

// ================= HELPER FUNCTIONS =====================

void applyMotorCommand(Motor &motor, int cmd)
{
  cmd = constrain(cmd, -PWM_MAX, PWM_MAX);

  if (cmd > 0)
  {
    motor.forward(cmd);
  }
  else if (cmd < 0)
  {
    motor.reverse(-cmd);
  }
  else
  {
    motor.coast();
  }
}

bool parseCommand(String line, int &m1, int &m2)
{
  line.trim();

  int commaIndex = line.indexOf(',');
  if (commaIndex < 0) return false;

  String s1 = line.substring(0, commaIndex);
  String s2 = line.substring(commaIndex + 1);

  s1.trim();
  s2.trim();

  m1 = s1.toInt();
  m2 = s2.toInt();

  return true;
}

void handleSerial()
{
  while (Serial.available())
  {
    char c = Serial.read();

    if (c == '\n')
    {
      int m1 = 0, m2 = 0;

      if (parseCommand(serialLine, m1, m2))
      {
        applyMotorCommand(motor1, m1);
        applyMotorCommand(motor2, m2);

        lastCommandTime = millis();

        Serial.print("CMD -> M1: ");
        Serial.print(m1);
        Serial.print("  M2: ");
        Serial.println(m2);
      }

      serialLine = "";
    }
    else if (c != '\r')
    {
      serialLine += c;
    }
  }
}

// ================= MAIN LOOP ============================

void loop()
{
  static unsigned long lastControlUpdate = 0;

  handleSerial();

  if (millis() - lastControlUpdate >= 5)
  {
    motor1.updateCurrentControl();
    motor2.updateCurrentControl();
    lastControlUpdate = millis();
  }

  // safety timeout: stop if commands stop arriving
  if (millis() - lastCommandTime > COMMAND_TIMEOUT_MS)
  {
    motor1.coast();
    motor2.coast();
  }
}
