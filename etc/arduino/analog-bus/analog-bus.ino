int i        = 0;
int npins    = 5;
int apins[]  = {A0, A1, A2, A3, A4};

void setup() {
  Serial.begin(9600);
}

void loop() {
  for (i=0; i<npins-1; i = i + 1) {
    Serial.print(analogRead(apins[i]));
    Serial.print("\t");
  }
  Serial.print(analogRead(apins[i]));
  Serial.println();
  delay(1000);
}
