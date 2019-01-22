# measurement-automation-tools
A collect of python tools for automating optical and electrical measurements using standard scientific equipment.

Included are example .tsp scripts to automate diode sweeps using Keithley 2636 or 2604 source measure units (SMUs), and code to control various standard scientific equipment such as Keysight U2722A SMUs, Stanford Research Systems lock-in amplifiers, and OBIS coherent lasers. 

experimentController.py provides an example GUI that can easily be edited to allow for various experimental input parameters to be controlled when running repetitive tests. In this example, the GUI is configured to run various voltage sweeps on an LED with simultaneous control of an OBIS laser and measurements using a lock-in amplifier.

## Other Resources
Some of the Keithley control functions are borrowed from: https://github.com/AFMD/keithley-2636
https://sweep-me.net/
