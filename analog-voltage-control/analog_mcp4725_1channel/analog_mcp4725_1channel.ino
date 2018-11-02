/**************************************************************************/
/*! 
    @file     trianglewave.pde
    @author   Adafruit Industries
    @license  BSD (see license.txt)

    This example will generate a triangle wave with the MCP4725 DAC.   

    This is an example sketch for the Adafruit MCP4725 breakout board
    ----> http://www.adafruit.com/products/935
 
    Adafruit invests time and resources providing this open source code, 
    please support Adafruit and open-source hardware by purchasing 
    products from Adafruit!
*/
/**************************************************************************/
#include <Wire.h>
#include <Adafruit_MCP4725.h>

String inString = "";    // string to hold input

Adafruit_MCP4725 dac;

void setup(void) {
  Serial.begin(9600);
  Serial.println("Hello!");

  // For Adafruit MCP4725A1 the address is 0x62 (default) or 0x63 (ADDR pin tied to VCC)
  // For MCP4725A0 the address is 0x60 or 0x61
  // For MCP4725A2 the address is 0x64 or 0x65
  dac.begin(0x62);
    
  Serial.println("Input integer");
}

void loop(void) {
    int counter;
    // Run through the full 12-bit scale for a triangle wave
    // Read serial input:
    while (Serial.available() > 0) {
      int inChar = Serial.read();
      if (isDigit(inChar)) {
        // convert the incoming byte to a char and add it to the string:
        inString += (char)inChar;
        //Serial.println(inString);
      }
      // if you get a newline, print the string, then the string's value:
      if (inChar == '\n') {
        Serial.print("Value:");
        Serial.println(inString.toInt());
        Serial.print("String: ");
        Serial.println(inString);
        counter = inString.toInt();
        // clear the string for new input:
        inString = "";
      }
      dac.setVoltage(counter, false);
    }
}
