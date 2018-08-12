--[[
   Example for two channel sweep for LED and photo detector test.
   
   Tested with:  2636B, firmware 3.2.1
   
   SMUA:  applies voltage sweep to an LED
   
   SMUB:  for each point in voltage sweep of SMUA, SMUB reads the current from a photo diode.
          To behave as a current meter, force 0 volts and measure current.

]]


function reset_buffers(smu)
    -- Prepare the Reading Buffers
	smu.nvbuffer1.clear()
	smu.nvbuffer1.appendmode		= 1
	smu.nvbuffer1.collecttimestamps	= 1
	smu.nvbuffer2.clear()
	smu.nvbuffer2.appendmode		= 1
	smu.nvbuffer2.collecttimestamps	= 1

end


function InitTSPLinkTriggers(nodenum)
    -- nodenum is the TSP-Link node number of the 26xxB
    -- three TSP link triggers; clear them all
    for i = 1, 3 do
	  node[nodenum].tsplink.trigger[i].clear()
	  node[nodenum].tsplink.trigger[i].mode	= tsplink.TRIG_FALLING
	end
end

function LIV_test(show_data)
	InitTSPLinkTriggers(1)
	
	-- clear the reading buffers
    reset_buffers(node[1].smua)
    reset_buffers(node[1].smub)

    -- clear status
    --status.reset()

    --setup status for SRQ on USER condition
    --status.operation.user.condition = 0  -- init to zero
    --status.operation.user.enable = status.operation.user.BIT0
    --status.operation.user.ptr = status.operation.user.BIT0
    --status.operation.enable = status.operation.USER  -- bit12
    --status.request_enable = status.OSB  -- bit7	
		
	-- program an event blender to raise an event when
    -- both smua AND smub have completed their measurements.
    -- This will keep the two smu channels in synchronization
    trigger.blender[1].reset()
    trigger.blender[1].orenable         = false  -- false means use AND logic
    trigger.blender[1].stimulus[1]      = node[1].smua.trigger.MEASURE_COMPLETE_EVENT_ID
    trigger.blender[1].stimulus[2]      = node[1].smub.trigger.MEASURE_COMPLETE_EVENT_ID

	-- when event blender stimuli occur and event is raised, use it as stimulus for tsplink trigger
	tsplink.trigger[1].stimulus	= trigger.blender[1].EVENT_ID

	-- Turn the outputs on
	smua.source.output					= smua.OUTPUT_ON
	smub.source.output					= smub.OUTPUT_ON
	

	-- Start the trigger model execution
	smub.trigger.initiate()
	smua.trigger.initiate()   
		
	tsplink.trigger[1].assert()  -- issue first trigger to get things started
	

	-- Wait until the sweep has completed
	waitcomplete()
	
    -- SRQ only works with GPIB
	--assert SRQ
	--status.operation.user.condition = status.operation.user.BIT0

	-- Turn the output off
	smua.source.output					= smua.OUTPUT_OFF
	smub.source.output					= smub.OUTPUT_OFF

    if show_data == true then
	   -- Print the data back to the Console in tabular format
	   print("Index \t Node 1 SMUA Voltage\tNode 1 SMUA Current\tNode 1 SMUB Voltage\tNode 1 SMUB Current")
	   for x=1,smua.nvbuffer1.n do
		  -- Voltage readings are in nvbuffer2.  Current readings are in nvbuffer1.
		  print(string.format("%d",x), 
		        string.format("%5.3f",smua.nvbuffer2[x]), 
		        smua.nvbuffer1[x], 
		        smub.nvbuffer2[x], 
		        smub.nvbuffer1[x])
	   end
	end
	
end  -- end LIV_test function


function VSweep(smu, start, stop, numPoints, limitI, nplc, remoteSense)
	smu.source.func					= smu.OUTPUT_DCVOLTS
		
	if (remoteSense == true) then
		smu.sense					= smu.SENSE_REMOTE
	else
		smu.sense					= smu.SENSE_LOCAL
	end
	smu.source.autorangev			= smu.AUTORANGE_OFF
	smu.source.rangev				= math.max(math.abs(start), math.abs(stop))
	smu.source.levelv				= 0
	smu.source.limiti				= limitI

	-- allow limited auto ranging
	smu.measure.autozero			= smu.AUTOZERO_ONCE
	smu.measure.autorangei			= smu.AUTORANGE_ON
	smu.measure.lowrangei           = 1e-6
	smu.measure.nplc				= nplc
	smu.measure.delay				= 0
	
	-- Configure SMU Trigger Model for Sweep
	smu.trigger.source.linearv(start, stop, numPoints)
	smu.trigger.source.limiti		= limitI
	smu.trigger.measure.action		= smu.ENABLE
	smu.trigger.measure.iv(smu.nvbuffer1, smu.nvbuffer2)
	smu.trigger.endpulse.action		= smu.SOURCE_HOLD
	smu.trigger.endsweep.action		= smu.SOURCE_IDLE
	smu.trigger.count				= numPoints
	smu.trigger.arm.stimulus		= 0
	smu.trigger.source.stimulus		= tsplink.trigger[1].EVENT_ID -- do not source until tsplink trigger
	smu.trigger.measure.stimulus	= 0
	smu.trigger.endpulse.stimulus	= 0
	smu.trigger.source.action		= smu.ENABLE
end



-- **************************************************************
--
--    Main Program - Call the functions that were defined above
--
-- **************************************************************


reset()
errorqueue.clear()
smua.reset()
smub.reset()

-- USER INPUT
--These must be input when loaded by python
--local numSweepPts = 81
--local LEDstartV = 0
--local LEDstopV = 8
--local LED_current_limit = 0.04
--local photodector_current_limit = 0.1
--local NPLC = 10
-- END USER INPUT

    ---- Configure SMUs
    -- config the LED SMU:  sweep voltage and measure current
    --VSweep(smu, start, stop, numPoints, limitI, nplc, remoteSense)
    VSweep(smua, LEDstartV, LEDstopV, numSweepPts, LED_current_limit, NPLC, false)

    -- config the Photo Detector SMU:  force 0 volts and measure current
    VSweep(smub, 0, 0, numSweepPts, photodector_current_limit, NPLC, false)



LIV_test(false)   -- pass true to print data back to console
--for i = 1 , 3 do
   --timer.reset()
   
   --time = timer.measure.t()
   --print("Time to run the sweep: "..time)
   --print("****************************************")
--end