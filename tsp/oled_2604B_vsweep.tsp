-- Beep in excitement
--GGGD#BbGD#BbG
--[[
beeper.beep(0.5, 392)
delay(0.05)
beeper.beep(0.5, 392)
delay(0.05)
beeper.beep(0.5, 392)
delay(0.05)
beeper.beep(0.375, 311.13)
beeper.beep(0.125, 466.16)
beeper.beep(0.5, 392)
beeper.beep(0.375, 311.13)
beeper.beep(0.125, 466.16)
beeper.beep(1, 392)
]]
--[[

  coordinated sweep on smua and smub of a dual channel 2600B
  
  generates the Id-Vg curve for a FET
  
  the smu connected to the pd_ will not change the voltage value, but will measure
  pd_ current for each point in the sweep
  
  the smu connected to the oled_ will change voltage value for each.  Current measurements
  not needed from this smu.  If we were to enable measurements, they would be very small
  values (oled_ leakage) and would require appropriate settling time for the low level
  of current.

]]


function configSweep(smu, startv, stopv, points, nplc, limitI)
	-- Setup a buffer to store the result(s) in and start testing.
    smu.nvbuffer1.clear()
    smu.nvbuffer1.appendmode = 1
    smu.nvbuffer1.collecttimestamps = 1
    smu.nvbuffer1.collectsourcevalues = 1
	
	smu.source.func					= smu.OUTPUT_DCVOLTS
		
	if (remoteSense == true) then
		smu.sense					= smu.SENSE_REMOTE
	else
		smu.sense					= smu.SENSE_LOCAL
	end
	smu.source.autorangev			= smu.AUTORANGE_OFF
	smu.source.rangev				= math.max(math.abs(startv), math.abs(stopv))
	smu.source.levelv				= 0
	smu.source.limiti				= limitI

	-- allow limited auto ranging
	smu.measure.autozero			= smu.AUTOZERO_ONCE
	smu.measure.autorangei			= smu.AUTORANGE_ON
	smu.measure.lowrangei           = 1e-9 -- was 1e-6
	smu.measure.nplc				= nplc
	smu.measure.delay				= 0
	
    -- Reset trigger model
    smu.trigger.arm.stimulus = 0
    smu.trigger.source.stimulus = 0
    smu.trigger.measure.stimulus = 0
    smu.trigger.endpulse.stimulus = 0
    smu.trigger.arm.count = 1
    -- Configure the source action
    smu.trigger.source.linearv(startv, stopv, points)
    smu.trigger.source.limiti = limitI
    smu.trigger.source.action = smu.ENABLE
    smu.trigger.endpulse.action = smu.SOURCE_HOLD
    smu.trigger.endsweep.action = smu.SOURCE_IDLE
    -- Configure the measure action
    smu.trigger.measure.i(smu.nvbuffer1)
    smu.trigger.measure.action = smu.ENABLE
    -- Configure the sweep count
    smu.trigger.count = points
    
end  -- function configSweep() definition


-- Photodetector (pd) and oled smu's
function startSweep(pd_smu, oled_smu)

    -- overwrite some value setup in the configSweep() function
    -- measure current when sourcing voltage on oled
    oled_smu.trigger.measure.i(oled_smu.nvbuffer1)
  
    -- oled_ sources after pd_ sources the desired bias
    oled_smu.trigger.source.stimulus = pd_smu.trigger.SOURCE_COMPLETE_EVENT_ID
    
    -- measure pd_ current after each oled_ voltage is sourced
    pd_smu.trigger.measure.stimulus = oled_smu.trigger.SOURCE_COMPLETE_EVENT_ID
    
    
    -- output on, run the sweep and then turn the output off.
    pd_smu.source.output = pd_smu.OUTPUT_ON
    oled_smu.source.output = oled_smu.OUTPUT_ON
    
    -- start the oled_ first, so that is armed and can detect pd_ source complete event
    oled_smu.trigger.initiate()
    pd_smu.trigger.initiate()
    
    waitcomplete()
    
    pd_smu.source.output = pd_smu.OUTPUT_OFF
    oled_smu.source.output = oled_smu.OUTPUT_OFF

end -- function

reset()
errorqueue.clear()
smua.reset()
smub.reset()
--display.clear()

-- User variables
--local numSweepPts = 81
--local startV = 0
--local stopV = 8
--local OLED_current_limit = 0.04
--local pd_current_limit = 0.1
--local NPLC = 1

oled_smu = smua
pd_smu = smub


--configSweep(smu, startv, stopv, points)
configSweep(pd_smu, 0, 0, numSweepPts, NPLC, pd_current_limit)
configSweep(oled_smu, startV, stopV, numSweepPts, NPLC, OLED_current_limit)

startSweep(pd_smu, oled_smu)