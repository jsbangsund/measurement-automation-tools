--[[
   Tested with:  2636B, firmware 3.2.1
   
   SMUA:  applies fixed voltage and measures current transient
   Based on this example:
   https://forum.tek.com/viewtopic.php?t=138682
]]

-- USER INPUT
--These must be input when loaded by python
--local interval_s = 0.002 -- measurement interval in s
--local duration_s = 10 -- how long to measure for in s
--local current_level = 1e-3
--local voltage_limit = 20
--local current_range = 10e-3
--local voltage_range = 20
-- END USER INPUT

reset()
errorqueue.clear()

smua.source.output = 1
smua.source.func=0 -- 0=DC_AMPS
smua.source.rangei = current_range  -- set fixed source range
smua.source.limitv = voltage_limit
smua.source.leveli = current_level  -- apply bias


smua.nvbuffer1.clear()
smua.nvbuffer1.collecttimestamps = 1
smua.nvbuffer1.collectsourcevalues = 1

smua.measure.rangev = voltage_range  -- set fixed measure range
smua.measure.autozero = smua.AUTOZERO_ONCE
smua.measure.interval = interval_s  -- minimum ~0.001
smua.measure.nplc = (interval_s - 100e-6)*localnode.linefreq
smua.measure.count = duration_s / interval_s


smua.trigger.measure.action = smua.ENABLE
smua.trigger.measure.v(smua.nvbuffer1)
smua.trigger.count = 1
smua.trigger.initiate()
waitcomplete()

smua.source.output = 0

--print("TimeStamps,Current")
--for i = 1, smua.nvbuffer1.n do
--  print(smua.nvbuffer1.timestamps[i]..","..smua.nvbuffer1.readings[i])
--end