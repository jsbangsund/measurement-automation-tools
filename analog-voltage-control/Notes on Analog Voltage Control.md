## Notes on final two-channel build for Catherine

Our goal is to output a voltage signal that ranges from 0 - 2 V with ~2 mV resolution in order to set the flow rate on a mass flow controller. The mass flow controller can be controlled remotely by supplying a voltage signal of 0 - 5 V, where 5 V corresponds to the maximum flow rate, 200 standard cubic centimeters per minute (SCCM). Being able to control this remotely with a microcontroller (i.e. an Arduino) allows for this to be controlled with software, rather than a tedious manual potentiometer. For Catherine's deposition system, the useful range is only 0 - 50 SCCM with a required resolution of ~0.1 SCCM. This means that the required voltage resolution is 0.1 SCCM / 200 SCCM * 5 V = 2.5 mV. As discussed above, the actual voltage reference we will be using is 4.096 V, giving a resolution requirement of 2.05 mV. For a 12-bit DAC, the maximum resolution is 3.3 V / 2^12 = 3.3 / 4096 = 0.8 mV. In reality, the resolution is probably lowered slightly by inaccuracies in Vout, but the stability of the output is quite high.

Using an arduino nano, two [MCP4725](https://www.adafruit.com/product/935) breakout boards, and an [LM4040 breakout board](https://www.adafruit.com/product/2200), all soldered on to a half-sized permaproto board from adafruit. See the fritzing drawing for more detail.

The LM4040 serves as a stable voltage reference for the Arduino. The internal reference voltage in the Arduino is not stable and would  be susceptible to drift over time, limiting both the precision and accuracy of the voltage output. This board takes an input voltage (Vin) of +5V (which we can conveniently supply from the +5V pin of the Arduino) and an input ground, which is tied to the GND pin of the Arduino. The LM4040 outputs two reference voltages: 2.048 V and 4.096 V, each with an accuracy of +/- 0.1%. We will just use the 4.096 reference voltage (actual measurement for this chip appears to be 4.097 V), and we will connect this to the REF pin on the Arduino and also to the +5V remote reference voltage pin on the mass flow controllers.

The MCP4725 breakout boards are 12-bit Digital-to-Analog Converters (DAC), which means they can convert a digital signal (integers from 0 to (2^12)-1 or 4095) to an analog voltage (ranging from ~0 V to the reference voltage). The reference voltage we will use for the MCP4725 boards is the +3.3V pin from the Arduino (which is stabilized by the LM4040, as it is referencing the REF pin). The actual voltage in our circuit is ~3.244 V. This voltage goes to the Vdd pin on the MCP4725 board. Then, we hook up the A4 pin and A5 pins of the Arduino to the SDA and SCL pins of the MCP4725, respectively. For one of the MCP4725 boards, the A0 pin is pulled up to Vdd, which gives this board a different I2C address (Hex 0x63 instead of 0x62).

Arduino code to run this can be found in Arduino\dual_channel\dual_channel.ino

A python GUI to control the chips is included in analogVoltageController.py



## Other notes on analog voltage control

To quote this [stackexchange post](https://arduino.stackexchange.com/questions/31664/how-to-output-a-true-analog-voltage-at-output-pin), there are three general ways to achieve a constant voltage source controlled by an arduino:

1. Use an Arduino Due which has a built-in DAC which outputs a real voltage.
2. Add an external DAC chip (such as the MCP4821/2) to create the voltage for you
3. Use a low-pass filter (R-C network) on a PWM pin.

## Easiest solution: MCP4725 and an I2C multiplexer

The [MCP4725](https://www.adafruit.com/product/935) is a cheap DAC breakout board from Adafruit, and presents a very low barrier for setting up a constant voltage output. There's documentation and a tutorial [here](https://learn.adafruit.com/mcp4725-12-bit-dac-tutorial/download); a pdf of this tutorial is included in this folder. 

To control four MCP4725 chips from a single Arduino, we need an [I2C multiplexer](https://learn.adafruit.com/adafruit-tca9548a-1-to-8-i2c-multiplexer-breakout/overview). But, for now, we only need two channels, so we can get away with using two addresses on the MCP4725 chips -- one chip can be set to a different address by pinning A0 to Vdd.

See [this trello card]( https://trello.com/c/kXUOMFbO/3-analog-voltage-control-for-mass-flow-controllers-and-led-power-feedback ) for more notes on how to do this.

We also need a stable input voltage reference to ensure that our setpoint doesn't drift. The easiest way to do this is using the adafruit [LM4040 breakout board](https://www.adafruit.com/product/2200).

## Arduino Due

The Arduino Due has two 12-bit DAC pins. Also, the output is only to 3.3V, so you would need some sort of amplification ([example here](https://create.arduino.cc/projecthub/ArduPic/how-to-modify-analog-output-range-of-arduino-due-6edfb5)) to achieve 0 - 5 V output. For Catherine's application of controlling four mass flow controllers with a 0-5V output, this would be clunky, because you would need two Arduino Due's. This could be an easy option for controlling the LED power via TTL for our optical degradation boxes. 

## RC filter

The RC filter option will be slow and have limited resolution. This would probably be fine in most cases, but I think it would be best to go for the external DAC chip to get the best performance (whether or not we need it). 

 More detail on RC filter approach here:
 https://www.youtube.com/watch?v=AkSm1W8xdKY 

 ## Other DAC chip options and links

This four channel DAC seems like a good option, though a bit pricier ($80):
 https://shop.controleverything.com/products/ad5696-16-bit-4-channel-digital-to-analog-converter
 Cheap DAC breakout board (probably one of the easiest ways to use this):
 https://www.adafruit.com/product/935
 And documentation:
 https://learn.adafruit.com/mcp4725-12-bit-dac-tutorial/download
 Forum discussion on a four channel DAC. Not super informative:
 https://forum.arduino.cc/index.php?topic=508454.0
 Multiple DACs on a single arduino nano:
 http://ua726.co.uk/2011/09/25/multiple-mcp4922-spi-dacs-on-an-arduino/
 Another forum for four channel options:
 https://forum.arduino.cc/index.php?topic=385741.0
 The MCP4728 is a 4 channel, 12 bit DAC. Here is discussion about a library to use this with arduino
 https://forum.arduino.cc/index.php?topic=51842.0
 Code for the library can be found here, but it is not very up to date:
 https://code.google.com/archive/p/neuroelec/downloads
 More up to date here:
 https://www.arduinolibraries.info/libraries/mcp4728
 Here is a purchase link on digikey:
 https://www.digikey.com/product-detail/en/microchip-technology/MCP4728T-E-UN/MCP4728T-E-UNCT-ND/5358293 

 Breadboard / arduino holder for 3D printing:
 https://www.thingiverse.com/thing:2205403 