/**************************************************************************/
/*! 
    @file     dual_channel.pde
    @author   John Bangsund
    @license  BSD (see license.txt)
    Control two MCP4725 DACs to output constant voltage outputs
    Uses the Adafruit MCP4725 breakout board
    ----> http://www.adafruit.com/products/935

    If having trouble with this uploading on an arduino nano, use:
    Processor: "ATmega328P (Old Bootloader)"

    Download the Adafruit_MCP4725 library here: https://github.com/adafruit/Adafruit_MCP4725
    Then copy that library directory to C:\Program Files (x86)\Arduino\libraries\
*/
/**************************************************************************/
#include <Wire.h>
#include <Adafruit_MCP4725.h>

String inString = "";    // string to hold input
char active_dac = 'A'; // currently active dac

Adafruit_MCP4725 daca;
Adafruit_MCP4725 dacb;

void setup(void) {
  Serial.begin(9600);
  //Serial.println("Hello!");

  // For Adafruit MCP4725A1 the address is 0x62 (default) or 0x63 (ADDR pin tied to VCC)
  // For MCP4725A0 the address is 0x60 or 0x61
  // For MCP4725A2 the address is 0x64 or 0x65
  daca.begin(0x62);
  dacb.begin(0x63);
    
  //Serial.println("Input integer");
}

void loop(void) {
    int counter;
    // Run through the full 12-bit scale for a triangle wave
    // Read serial input:
    while (Serial.available() > 0) {
      // incoming string should have form: A#### or B####
      // where A or B is the channel, and #### is 0 to 4095
      char inChar = Serial.read();
      if (isAlpha(inChar)) {
          // turn laser on
          if(inChar=='A'){
            active_dac='A';
          }
            // turn current on
          if(inChar=='B'){
            active_dac='B';
          }
          if(inChar=='Q'){
            Serial.print(active_dac);
          }
      }
      if (isDigit(inChar)) {
        // convert the incoming byte to a char and add it to the string:
        inString += (char)inChar;
        //Serial.println(inString);
      }
      // if a newline is sent, set the voltage value
      if (inChar == '\n') {
        if(inString!=""){
          counter = inString.toInt();
          // clear the string for new input:
          inString = "";
          if(active_dac=='A'){
                //Serial.print("Set A to:");
                //Serial.println(counter);
                daca.setVoltage(counter, false);
              }
          if(active_dac=='B'){
                //Serial.print("Set B to:");
                //Serial.println(counter);
                dacb.setVoltage(counter, false);
              }
        }
      }
      
    }
}
