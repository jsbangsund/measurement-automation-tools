# measurement-automation-tools
A collection of python tools for automating optical and electrical measurements using standard scientific equipment. If you find this code useful, please cite our [publication](https://doi.org/10.1126/sciadv.abb2659):

>J. S. Bangsund, J. R. Van Sambeek, N. M. Concannon, R. J. Holmes, Sub–turn-on exciton quenching due to molecular orientation and polarization in organic light-emitting devices. Sci. Adv. 6, eabb2659 (2020). DOI: 10.1126/sciadv.abb2659

The photoluminescence quenching measurements in this article were performed using the `lockinSweep` function in `experimentController.py`.

`experimentController.py` provides an example GUI that can easily be edited to allow for various experimental input parameters to be controlled when running repetitive tests. In this example, the GUI is configured to run various voltage sweeps on an LED with simultaneous control of an OBIS laser and measurements using a lock-in amplifier.

Also included are example .tsp scripts to automate diode sweeps using Keithley 26XX (2636 or 2604) source measure units (SMUs), and code to control various standard scientific equipment such as Keysight U2722A SMUs, Stanford Research Systems lock-in amplifiers (SR850), and OBIS coherent lasers. 

## Other Resources
Some of the Keithley control functions are borrowed from: https://github.com/AFMD/keithley-2636

https://sweep-me.net/
