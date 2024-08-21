int mq4 = A0;
int mq4Value = -1;

void setup() {
  Serial.begin(9600);
}

void loop() {
  // read the value from the sensor:
  mq4Value = analogRead(mq4);
  Serial.println(String(mq4Value, DEC));
  delay(1000);
}
