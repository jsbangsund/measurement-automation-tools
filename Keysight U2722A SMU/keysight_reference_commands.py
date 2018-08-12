# Keysight commands
# Initialization
self.keysight[dev].write('*RST') # Not sure what this does yet

# Sweep
self.keysight[dev].write('sense:current:NPLC 10, (@1)') # set number of power line cycles per measurement to 10 on channel 1
self.keysight[dev].write('sense:sweep:points 1000, (@1)')  # set number of points in the sweep
self.keysight[dev].query('sense:current:aperture? (@1)') # request
self.keysight[dev].write('sense:sweep:Tinterval 10, (@1)') # set time interval between samples in milliseconds

# Source Range
self.keysight[dev].write('source:voltage:range R20V, (@1)') # Set voltage range to 20 volts. R2V is the other option
self.keysight[dev].write('source:current:range R10mA, (@1)') # Set current range to 1 - 10 mA on channel 1
# Other ranges: R1uA, R10uA, R100uA, R1mA, R120mA range

# Set compliance voltage and current
self.keysight[dev].write('source:voltage:limit 20, (@1)')
self.keysight[dev].write('source:current:limit 0.01, (@1)')

# Source
self.keysight[dev].write('source:current 0.001, (@1)') # Source 0.001 A on channel 1

# Turn output on or query output state
self.keysight[dev].query('output? (@1)') # Check the output status (on or off) of channel 1
self.keysight[dev].write('output ON, (@1)') # turn on output on channel 1

# Measurement
self.keysight[dev].query('measure:voltage? (@2)') # Measure voltage for channel 2 
self.keysight[dev].query('measure:current? (@2)')
self.keysight[dev].query('measure:array:current? (@2)') # This measurement array could be used for sweeps
