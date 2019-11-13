# imports
#import visa
import numpy as np
import os
import csv
import time
import datetime
import tkinter as tk
from tkinter.filedialog import askopenfilename, askdirectory
from tkinter.ttk import Frame, Button, Style,Treeview, Scrollbar, Checkbutton
from functools import partial
import serial
# This program sweeps current on a device and measures
# lock-in PL
# TODO add re-connect to instrument button?
class VoltageController(Frame):
    def __init__(self,parent):
        #### USER DEFINED
        self.arduinoAddress = 'COM3'
        self.window_title = "Mass Flow Control"
        self.channels = ["A","B"]
        self.V_calibration = {i:None for i in self.channels} # initialize correction factor
        self.show_keithley = False
        self.smu_address_default = ""
        self.smu_address = ""
        self.complianceV=5
        self.max_V_out = 3.2467 # Measured maximum output voltage
        self.upper_reference_V = 4.097 # Measured reference output from LM4040
        #### End user defined parameters
        
        self.arduino = serial.Serial(self.arduinoAddress,9600)
        
        Frame.__init__(self, parent)  
        self.parent = parent
        self.configure_gui()
                
    def configure_gui(self): 
        # Master Window
        self.parent.title(self.window_title)
        self.style = Style()
        self.style.theme_use("default")

        # Test Mode Frame
        frame_setpoints=Frame(self)
        frame_setpoints.pack()
        self.s_setpoints = {}
        self.b_set_setpoints = {}
        self.l_actual_flow = {}
        self.l_integer = {}
        tk.Label(frame_setpoints,text="Setpoint").grid(row=0,column=1,sticky=tk.W,padx=1, pady=1)
        tk.Label(frame_setpoints,text="Actual").grid(row=0,column=2,sticky=tk.W,padx=1, pady=1)
        tk.Label(frame_setpoints,text="Integer").grid(row=0,column=3,sticky=tk.W,padx=1, pady=1)
        for i,ch in enumerate(self.channels):
            self.s_setpoints[ch] = tk.StringVar()
            tk.Label(frame_setpoints,text="Channel " + str(ch) + " (SCCM)"
                ).grid(row=i+1,column=0,sticky=tk.W,padx=1, pady=1)#.pack(side=tk.LEFT)
            tk.Entry(frame_setpoints,textvariable=self.s_setpoints[ch],width=10
                ).grid(row=i+1,column=1,sticky=tk.W)
            self.l_actual_flow[ch] = tk.Label(frame_setpoints,text="00.00")
            self.l_actual_flow[ch].grid(row=i+1,column=2,sticky=tk.W,padx=1, pady=1)
            self.l_integer[ch] = tk.Label(frame_setpoints,text="0000")
            self.l_integer[ch].grid(row=i+1,column=3,sticky=tk.W,padx=1, pady=1)
            self.b_set_setpoints[ch] = Button(
                frame_setpoints,text="Set", 
                command=partial(self.set_setpoint,ch))
            self.b_set_setpoints[ch].grid(row=i+1,column=4,sticky=tk.W,padx=1, pady=1)
        
        # Source control buttons
        frame_buttons=Frame(self)
        frame_buttons.pack()
        # Turn on all sources
        tk.Button(frame_buttons,text="Turn Sources On", bg="lime",
                command=self.turn_on_sources).grid(row=0,column=0,sticky=tk.W,padx=1, pady=1)
        # Set all sources to zero
        tk.Button(frame_buttons,text="Set Sources to 0", bg="red",
                command=self.turn_off_sources).grid(row=0,column=1,sticky=tk.W,padx=1, pady=1)
        # Functions for measuring with Keithley
        if self.show_keithley:
            self.rm = visa.ResourceManager()
            self.resources = self.rm.list_resources()
            self.configure_keithley_widgets()  
        # Style Configuration
        Style().configure("defaultState.TButton", foreground='black', background='light grey')
        Style().configure("onState.TButton", foreground='black', background='red')
        Style().map("onState.TButton",
                    background=[('disabled', 'grey'),
                                ('pressed', 'red3'),
                                ('active', 'red2')])
        
        self.pack(fill=tk.BOTH, expand=1)
    def configure_keithley_widgets(self):
        frame_keithley = Frame(self)
        frame_keithley.pack()
        self.l_smu_address = tk.Label(frame_keithley, text='Pick SMU address:')
        self.l_smu_address.grid(row=0, column=0, sticky=tk.W)
        self.s_smu_address = tk.StringVar()
        self.s_smu_address.set(self.smu_address)
        self.o_smu_address = tk.OptionMenu(
            frame_keithley, self.s_smu_address,*self.resources,
            command=self.connect_to_smu)
        self.o_smu_address.grid(row=0,column=1, sticky=tk.W)
        self.configure_resource_optionmenu()
        ##### Connect buttons
        #self.c_connect = Frame(self.c_top)
        #self.c_connect.pack(fill=X, expand=True)
        self.b_connect = tk.Button(frame_keithley, command=self.connect_to_smu)
        self.b_connect.configure(text="Connect", background= "yellow")
        self.b_connect.grid(row=0, column=2, sticky=tk.E, padx=5)
        self.b_calibrate_channelA = tk.Button(frame_keithley, command=partial(self.calibrate_channels,"A"))
        self.b_calibrate_channelA.configure(text="Calibrate A", background= "grey")
        self.b_calibrate_channelA.grid(row=0, column=3, sticky=tk.E, padx=5)
        self.b_calibrate_channelB = tk.Button(frame_keithley, command=partial(self.calibrate_channels,"B"))
        self.b_calibrate_channelB.configure(text="Calibrate B", background= "grey")
        self.b_calibrate_channelB.grid(row=0, column=4, sticky=tk.E, padx=5)
        tk.Label(frame_keithley, text='Voltage Reading:').grid(row=1,column=0,padx=5,sticky=tk.E)
        self.l_voltage = tk.Label(frame_keithley, text='000.0 mV')
        self.l_voltage.grid(row=1,column=1,padx=5,sticky=tk.W)
    def configure_resource_optionmenu(self):
        # Only display keithley or GPIB addresses
        # Keithley addresses have form USB0::0x05E6::0x26##::7 digit SN::INSTR
        self.display_resources = []
        for resource in self.resources:
            if ('USB0::0x05E6::0x26' in resource) or ('GPIB0' in resource):
                # Add the resource address and vendor info to the option menu
                hardware_info = self.get_hardware_label(resource)
                if not hardware_info=='Unknown':
                    self.display_resources.append(resource + '--' + hardware_info)
        # https://stackoverflow.com/questions/28412496/updating-optionmenu-from-list
        menu = self.o_smu_address["menu"]
        menu.delete(0, "end")
        for string in self.display_resources:
            menu.add_command(label=string,
                             command=lambda value=string.split('--')[0]: self.s_smu_address.set(value))
        # reset address to default
        self.s_smu_address.set(self.smu_address_default)
    def get_hardware_label(self,resource):
        # Check for known hardware types and make a label
        try:
            r = self.rm.open_resource(resource)
            hardware_info = r.query("*IDN?")
            if 'OK\r\n' in hardware_info:
                # The "OK\r\n" message is sent as a handshake from Obis lasers
                # Turn hand-shaking off and then ask for the info again
                r.write('system:communicate:handshaking OFF')
                hardware_info = r.query("*IDN?")
            # Check for known instruments
            if 'Keithley' in hardware_info:
                model_number = hardware_info.split(',')[1].split(' Model ')[1]
                serial_number = hardware_info.split(',')[2][1:]
                label = 'Keithley ' + model_number + ' SN: ' + serial_number
            elif 'Stanford' in hardware_info:
                label = 'Lock-in Amplifier ' + hardware_info.split(',')[1]
            elif 'HEWLETT' in hardware_info:
                label = 'Parameter Analyzer ' + hardware_info.split(',')[1]
            elif 'Coherent' in hardware_info:
                wavelength = r.query('system:information:wavelength?')
                if 'OK' in wavelength:
                    r.write('system:communicate:handshaking OFF')
                    wavelength = r.query('system:information:wavelength?')
                label = 'Coherent ' + wavelength.strip() + 'nm laser'
            else:
                label = 'Unknown: ' + hardware_info.strip()
            r.close()
        except Exception as e:
            #print(e)
            label='Unknown'
        return label
    def connect_to_smu(self):
        self.smu_address = self.s_smu_address.get()
        self.keithley = self.rm.open_resource(self.smu_address)
        self.initializeKeithley(self.keithley)
        print('keithley connected')
        self.b_connect.configure(background='green2')
    def calibrate_channels(self,ch):
        print("calibrating channel " + ch)
        setpoints = np.arange(0,4096,1)
        voltages = np.zeros(setpoints.shape)
        self.keithley.write('smua.source.leveli=0')
        self.keithley.write('smua.source.output=1')
        self.keithley.write('smua.measure.autorangev=1')
        for i,setpt in enumerate(setpoints):
            self.arduino.write((str(ch)+str(setpt)+'\n').encode())
            self.l_actual_flow[ch].configure(text=str(setpt))
            time.sleep(0.2)
            voltages[i] = self.readVoltage()
            self.l_voltage.configure(text="{:.2f}".format(voltages[i]*1e3) + " mV")
            self.parent.update()
        np.savetxt('Channel'+ch+'_calibration.csv',np.vstack((setpoints,voltages)).T,
                  delimiter=',',header='Setpoints,Voltages')
    def prep_measure_stability(self,ch):
        self.start_time = time.time()
        self.set_setpoint(ch) # Turn on desired set-point
        self.file = 'Channel'+ch+'_stability.csv'
        header="Elapsed Time (hr),Output Voltage (V)\n"
        with open(self.file, 'a') as f:
            f.write(header)
        self.measure_stability(ch)
    def measure_stability(self,ch):
        voltage = self.readVoltage() # read voltage
        self.onTime = time.time() - self.startTime # record onTime
        self.l_voltage.configure(text="{:.2f}".format(voltages[i]*1e3) + " mV")
        # Update file
        with open(self.file, 'a') as f:
            f.write(str(self.onTime/3600.0)+','+
                    str(voltage)+'\n')
        # Update once every 20 seconds
        self.parent.after(int(20 * 1000),  partial(self.measure_stability,ch))
        
    def set_setpoint(self,ch):
        integer,actual_flow = self.convert_sccm_to_int(float(self.s_setpoints[ch].get()),ch)
        self.l_actual_flow[ch].configure(text='{:.2f}'.format(float(actual_flow)))
        self.l_integer[ch].configure(text=str(integer))
        self.arduino.write((str(ch)+str(integer)+'\n').encode())
    def convert_sccm_to_int(self,sccm,ch):
        # Get calibration if not yet loaded
        if self.V_calibration[ch] is None:
            self.V_calibration[ch] = np.genfromtxt("Channel"+ch+"_calibration.csv",
                                                   delimiter=',',skip_header=1)
        # Maximum SCCM output is 200
        # the upper reference output voltage is given by the LM4040
        sccm_per_volt = 200 / self.upper_reference_V
        V_out = sccm / sccm_per_volt # Needed output voltage
        if V_out > self.max_V_out:
            print('Maximum output voltage exceeded')
            V_out = self.max_V_out
        idx_min = np.abs(V_out - self.V_calibration[ch][:,1]).argmin()
        integer = int(self.V_calibration[ch][idx_min,0])
        #V_out * 4096 / self.max_V_out / MCF
        actual_flow=self.V_calibration[ch][idx_min,1]*sccm_per_volt
        return integer,actual_flow
    def turn_off_sources(self):
        for ch in self.channels:
            self.arduino.write((str(ch)+str(0)+'\n').encode())
    def turn_on_sources(self):
        for ch in self.channels:
            self.set_setpoint(ch)
        
    def initializeKeithley(self,keithley):
        keithley.write('reset()')
        keithley.timeout = 4000 # ms
        keithley.write('errorqueue.clear()')
        ch = 'a'
        keithley.write( 'smu'+ch+'.reset()')
        keithley.write( 'smu'+ch+'.measure.count=20') 
        keithley.write( 'smu'+ch+'.measure.nplc=1')
        keithley.write( 'smu'+ch+'.nvbuffer1.appendmode=0')
        keithley.write( 'smu'+ch+'.nvbuffer1.clear()')
        keithley.write( 'smu'+ch+'.source.func=0') # 0 is output_DCAMPS, 1 is output_DCVOLTS
        keithley.write( 'smu'+ch+'.source.limitv='+str(self.complianceV))
        keithley.write( 'smu'+ch+'.source.leveli=0')
        keithley.write( 'smu'+ch+'.source.output=0')
        keithley.write( 'smu'+ch+'.measure.autorangev=1')
        ch = 'b'
        keithley.write( 'smu'+ch+'.reset()')
        keithley.write( 'smu'+ch+'.measure.count=10')
        keithley.write( 'smu'+ch+'.measure.nplc=1')
        keithley.write( 'smu'+ch+'.nvbuffer1.appendmode=0')
        keithley.write( 'smu'+ch+'.nvbuffer1.clear()')
        keithley.write( 'smu'+ch+'.source.func=1') # 0 is output_DCAMPS, 1 is output_DCVOLTS
        keithley.write( 'smu'+ch+'.source.levelv=0')
        keithley.write( 'smu'+ch+'.measure.autorangei=1')
        keithley.write( 'smu'+ch+'.source.output=1')
        print('keithley initialized')
        
    def turnCurrentOn(self,I):
        print('current turned on')
        self.keithley.write( 'smua.source.leveli='+str(I))
        self.keithley.write( 'smua.source.output=1')
        
    def turnCurrentOff(self):
        print('current turned off')
        self.keithley.write( 'smua.source.output=0')   
    
    def turnVoltageOn(self,V):
        #print('voltage turned on')
        self.keithley.write( 'smua.source.func=1') # 0 is output_DCAMPS, 1 is output_DCVOLTS
        self.keithley.write( 'smua.source.levelv='+str(V))
        self.keithley.write( 'smua.source.output=1')
        
    def turnVoltageOff(self):
        #print('voltage turned off')
        self.keithley.write( 'smua.source.levelv=0')
        self.keithley.write( 'smua.source.func=0') # 0 is output_DCAMPS, 1 is output_DCVOLTS
        self.keithley.write( 'smua.source.output=0')    
        
    # reads the voltage from keithley of the specified device     
    def readVoltage(self):
        self.keithley.write('smua.nvbuffer1.clear()')
        self.keithley.write('smua.measure.v(smua.nvbuffer1)')
        sig = self.keithley.query('printbuffer(1,smua.nvbuffer1.n,smua.nvbuffer1)') 
        sig=[float(v) for v in sig.split(',')]
        return np.mean(sig)
        
    def readCurrent(self):
        self.keithley.write( 'smua.measure.autorangei=1')
        self.keithley.write('smua.nvbuffer1.clear()')
        self.keithley.write('smua.measure.i(smua.nvbuffer1)')
        sig = self.keithley.query('printbuffer(1,smua.nvbuffer1.n,smua.nvbuffer1)') 
        sig=[float(v) for v in sig.split(',')]
        return np.mean(sig)
        
    # reads device photodiode signal measured by keithley from channel b
    def keithleyDiodeRead(self,keithley):
        holder = []
        for x in range(0,self.keithleyReadingCount):
            keithley.write('smub.nvbuffer1.clear()')
            keithley.write('smub.measure.i(smub.nvbuffer1)')
            sig = keithley.query('printbuffer(1,smub.nvbuffer1.n,smub.nvbuffer1)') 
            sig=[float(v) for v in sig.split(',')]
            holder.append(sig)
        return np.mean(holder),np.std(holder)
    
    def loadTSP(self, tsp,tspInputDict):
        '''Load an anonymous TSP script into the K2636 nonvolatile memory'''
        tsp_dir = 'C:\\Users\\Lifetime\\Documents\\GitHub\\lifetimeTesting\\development\\tsp\\' # Put all tsp scripts in this folder
        
        self.keithley.write('loadscript')
        line_count = 1
        # First write user input variables
        for key, value in tspInputDict.items():
            self.keithley.write('local ' + key + ' = ' + str(value))
        # Now upload the rest of the code
        for line in open(str(tsp_dir + tsp), mode='r'):
            self.keithley.write(line)
            line_count += 1
        self.keithley.write('endscript')
        print ('Uploaded TSP script: ', tsp)
        
    def readBuffer(self):
        #'''Read specified buffer in keithley memory and return a pandas array'''
        #V = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)').split(',')]
        V = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer2.n, smua.nvbuffer2.readings)').split(',')]
        I = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)').split(',')]
        EL = [float(x) for x in self.keithley.query('printbuffer(1, smub.nvbuffer1.n, smub.nvbuffer1.readings)').split(',')]
        return V,I,EL
        
    def readBuffer_timestamps(self):
        #'''Read specified buffer in keithley memory and return a pandas array'''
        #V = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)').split(',')]
        times = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer2.n, smua.nvbuffer2.timestamps)').split(',')]
        V = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer2.n, smua.nvbuffer2.readings)').split(',')]
        I = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)').split(',')]
        EL = [float(x) for x in self.keithley.query('printbuffer(1, smub.nvbuffer1.n, smub.nvbuffer1.readings)').split(',')]
        return np.array(times),np.array(V),np.array(I),np.array(EL)
        
    def lockinSweep(self,during_deg=False):
        self.turnLaserOn()
        print('----------------------------------------')
        print('Beginning lock-in PL voltage sweep')
        start_time = time.time() # time the sweep
        # initialize data arrays for storage
        I1 = np.zeros(self.voltages.shape)
        I2 = np.zeros(self.voltages.shape)
        PL_avg = np.zeros(self.voltages.shape)
        PL_std = np.zeros(self.voltages.shape)
        for i,V in enumerate(self.voltages):
            self.turnVoltageOn(V) # set voltage
            I1[i] = self.readCurrent() # current at beginning of voltage step
            PL_avg[i],PL_std[i] = self.lockinRead() # measure PL
            I2[i] = self.readCurrent() # current at end of voltage step
            if not during_deg:
                try:
                    print('V=' + str(V) + ', J1/J2='+'{:.2f}'.format(I1[i]/I2[i]*100)
                        +'%, PL=' + '{:.2f}'.format(PL_avg[i]/PL_avg[0]*100)+'%')
                except:
                    print('print failed')
        # Turn off current
        self.turnVoltageOff()
        # Turn off laser
        self.turnLaserOff()
        end_time = time.time()
        print('sweep finished in ' + '{:.3f}'.format(end_time - start_time) + 's')    
        # Write file
        self.write_lockin_sweep_file(self.voltages,I1,I2,PL_avg,PL_std,during_deg=during_deg)
            
    def reset_SRQ(self):
        self.keithley.write('status.reset()')
    def fast_lockin_sweep(self,during_deg=False):
        '''
         NOTE: GPIB connection to keithley 26xx is required for synchronizing scans
         This function enables a faster sweep, measuring OLED current as a function of
         applied voltage (the sweep variable) on a keithley 26xx, as well as PL signal
         from an SR810 lock-in amplifier.
         The faster sweep is achieved by using a tsp script to sweep the keithley while
         simultaneously saving lock-in data to an internal buffer which is read after the
         sweep completes. Timing of the start of these scans may not be perfectly identical,
         since commands are sent sequentially, but is probably within a few ms. Timing
         for the end of the scan is achieved by waiting for a serial request (SRQ). This
         can only be done if the keithley is connected by GPIB (not by USB)
         '''
        n_points = int((self.stopV-self.startV)/self.stepV)+1 # number of sweep points
        # Here I am setting the scan rate to the maximum value that will not exceed
        # the buffer during the keithley sweep
        #est. scan time in s based on NPLC, with 10% cushion
        scan_time = (self.NPLC / 60 + self.delay) * n_points * 1.1
        max_srat = 8191 / scan_time # Maximum scan rate given the scan time to fill the buffer
        scan_rates = [62.5e-3,125e-3,250e-3,500e-3,1,2,4,8,16,32,64,128,256,512]
        set_srat = max(i for i in scan_rates if (max_srat-i)>0)
        with open(self.settings_file, 'a') as f:
            f.write('Lock-in scan rate:,'+str(set_srat)+'Hz'+'\n')
        print('----------------------------------------')
        print('Beginning synchronized voltage sweep')
        print('scan rate: ' +str(set_srat))
        print('NPLC: ' + str(self.NPLC))
        # Lock-in commands are based on the index within the list of possible values
        srat_idx = scan_rates.index(set_srat)
        #scan_rate = scan_rates[srat_idx]
        tspInputDict = {
            'numSweepPts':n_points,'LEDstartV':self.startV,'LEDstopV':self.stopV,
            'LED_current_limit':0.04,'photodector_current_limit':0.1,'NPLC':self.NPLC,
            'delay':self.delay}
        # Load the tsp file
        tsp_file = 'oled_vsweep_srq.tsp'
        self.loadTSP(tsp_file,tspInputDict)
        # Set-up the lock-in (see documentation on Pg. 87 (5-13) in SR810m.pdf)
        self.lockin.write('REST') # reset the buffer
        self.lockin.write('SEND 0') # Set to single shot scan (buffer won't be overwritten in loop)
        self.lockin.write('SRAT ' + str(srat_idx)) # Set the scan rate
        # Re-set the SRQ in case it was left on (crashed sweep for example)
        self.reset_SRQ()
        # start the sweep
        self.turnLaserOn()
        start_time = time.time() # time the sweep for troubleshooting purposes
        self.lockin.write('STRT') # start data collection on lock-in
        self.keithley.write('script.anonymous.run()') # start sweep on keithley
        try:
            self.keithley.wait_for_srq(timeout=int(scan_time*1.2*1000)) # wait for sweep to finish, give 20% buffer
        except visa.VisaIOError as e:
            # confirm that error is timeout. If so wait 10 more sec
            if 'VI_ERROR_TMO' in e.args[0]:
                print('timed out. Waiting a little longer')
                self.keithley.wait_for_srq(timeout=10000)
        self.lockin.write('PAUS')
        end_time = time.time() # May like to have a check if scan time is too short and then wait again
        self.turnLaserOff()
        print('sweep finished in ' + '{:.3f}'.format(end_time - start_time) + 's')
        # Read the lock-in buffer
        n_lockin_points = int(self.lockin.query('SPTS ?'))
        self.lockin.timeout = 10000 # ms, set high for reading long data string
        lockin_data_string = self.lockin.query('TRCA ? 0, ' + str(n_lockin_points-1))
        lockin_data = np.fromstring(lockin_data_string,sep=',')
        # Read the keithley buffer
        times,V,I,EL = self.readBuffer_timestamps()
        # Get equivalent times of lock-in scan based on scan rate
        # and substract 2 ms (approximate time it takes to start sweep)
        lockin_times = np.arange(0,lockin_data.shape[0],1)*(1/set_srat)-0.002
        # Trim last 10 ms of data (this is close to when sweep ends, could be noisy)
        filter_idx = np.where(np.logical_and(
            lockin_times>0,lockin_times<lockin_times[-1]-0.01))[0]
        lockin_times=lockin_times[filter_idx]
        # Bin and average lock-in datapoints based on keithley timestamps
        # Make arrays for avg and std of PL signal 
        # (binned over each voltage step)
        PL_avg = np.zeros(V.shape)
        PL_std = np.zeros(V.shape)
        # Get time constant in s (this line strips letters (us,ms,s, or ks) from oflt)
        tau = 1e-3*float(''.join(i for i in self.string_vars['oflt'].get() if i.isdigit()))
        print('tau: '+str(tau))
        print('lockin points: ' + str(n_lockin_points))
        for i,V_i in enumerate(V):
            # Select window start and end points based on timestamps
            # Trim first five time constants of data (takes 5xTau to settle)
            # May need to re-think timing here. It looks like the keithley takes a little while
            # to sweep
            t1 = times[i]-self.delay+tau*5
            if i < (len(V)-1):
                # subtract delay (this is settle time at next point 
                # before next measurement)
                t2 = times[i+1] - self.delay
            else:
                t2 = lockin_times[-1]
            bin_idx = np.where(np.logical_and(
                lockin_times>t1,lockin_times<t2))[0]
            if len(bin_idx)>0:
                PL_avg[i] = np.mean(lockin_data[bin_idx])
                PL_std[i] = np.std(lockin_data[bin_idx])
        self.write_file_sync_sweep(times,V,I,EL,PL_avg,PL_std,during_deg=during_deg)
        self.write_file_lockin_scan(lockin_times,lockin_data,during_deg=during_deg)
        print('file save completed')
    def keithleyTest(self):
        self.turnLaserOn()
        #PL_J,PL_J_err = self.keithleyDiodeRead()
        #self.writeLine(0,0,0,PL_J,PL_J_err)
        #print(PL_J)
        for V in self.voltages:
            # Condition device at reverse bias and measure PL again
            # self.turnVoltageOn(-2)
            # time.sleep(self.condition_time)
            # self.turnVoltageOff()
            
            # Take PL measurement with J off
            # PL,PL_err = self.lockinRead()
            # print(PL)
            
            # Measure PL with J on
            self.turnVoltageOn(V)
            time.sleep(1)
            PL_J,PL_J_err = self.keithleyDiodeRead(self.keithley)
            print(PL_J)
            
            # Measure EL and V (with laser on still)
            #EL = self.keithleyDiodeRead()
            EL=0
            J = self.readCurrent()
            #print(J)
            
            # Write line
            self.writeLine(J,EL,V,PL_J,PL_J_err)
        
        
        # Turn off current
        self.turnVoltageOff()
        
        # Turn off laser
        self.turnLaserOff()
        time.sleep(1)
    def keithleySweepTest(self):
        self.turnLaserOn()
        voltage,current,PL=self.voltageSweep(np.amin(self.voltages),
                        np.amax(self.voltages),
                        np.abs(self.voltages[1]-self.voltages[0]),
                        self.NPLC)#start,stop,step,nplc
        self.turnVoltageOff()
        self.turnLaserOff()
        # Write file
        for idx in range(0,len(voltage)):
            self.writeLine(current[idx],0,voltage[idx],PL[idx],0)
    def voltageTransient(self,tspInputDict,laser_on_time,laser_wait):
        # Typical values:
        # interval_s = 0.05
        # duration_s = 10
        # voltage_limit = 20
        # voltage_range = 200e-2,2,20,200
        # tspInputDict = {
                    # 'current_level':current,
                    # 'voltage_limit':voltage_limit,
                    # 'voltage_range':voltage_range,
                    # 'current_range':current_range,
                    # 'interval_s':interval_s,
                    # 'duration_s':duration_s,
                    # }
        tsp_file = 'voltage_transient.tsp'
        self.loadTSP(tsp_file,tspInputDict)
        # Turn laser on, wait 'laser_wait' seconds, hold 'laser_on_time' seconds
        # If laser_wait is positive, start transient before turning on laser
        # If laser_wait is negative, do the opposite
        if laser_wait>=0:
            # Now start transient measurement
            self.keithley.write('script.anonymous.run()')
            print('Measurement in progress...')
            time.sleep(laser_wait)
            self.turnLaserOn(sleep=False)
            # wait here should be in ms
            # Takes about 6.6 s for 473 laser to start, so wait that additional time
            self.parent.after(int((laser_on_time+6.6)*1000),  self.turnLaserOff)

        else:
            self.turnLaserOn(sleep=False)
            time.sleep(-laser_wait)
            # Now start transient measurement
            self.keithley.write('script.anonymous.run()')
            print('Measurement in progress...')
        
            # wait here should be in ms
            # Takes about 6.6 s for 473 laser to start, so wait that additional time
            self.parent.after(int((laser_on_time+6.6+laser_wait)*1000),  self.turnLaserOff)
        
        # Wait 'duration_s' + some fudge time to let test finish
        file_modifier='_I='+str(tspInputDict['current_level'])
        header='Time (s),Current (A)'
        self.parent.after(int((tspInputDict['duration_s']+3)*1000),self.readTransientBuffer,file_modifier,header)            
        
    def repeatCurrentTransient(self):
        # If test has been turned off, don't call function again
        if not self.test_running_bool:
            return
        # interval_s,duration_s,
        # voltage,voltage_range,current_limit,current_range,
        # laser_on_time,laser_wait
        # Typical values:
        # interval_s = 0.05
        # duration_s = 10
        # current_limit = 0.04
        # current_range = factors of 10 from 100e-12 to 1
        # Load tsp
        # tspInputDict = {
                    # 'voltage_level':voltage,
                    # 'current_limit':current_limit, # in A
                    # 'current_range':current_range,
                    # 'voltage_range':voltage_range,
                    # 'interval_s':interval_s,
                    # 'duration_s':duration_s,
                    # }
        tsp_file = 'current_transient.tsp'
        self.loadTSP(tsp_file,self.tspInputDict)
        # Turn laser on, wait 'laser_wait' seconds, hold 'laser_on_time' seconds
        # If laser_wait is positive, start transient before turning on laser
        # If laser_wait is negative, do the opposite
        if self.laser_wait_s>=0:
            # Now start transient measurement
            self.keithley.write('script.anonymous.run()')
            print('Measurement in progress...')
            time.sleep(self.laser_wait_s)
            self.turnLaserOn(sleep=False)
            # wait here should be in ms
            # Takes about 6.6 s for 473 laser to start, so wait that additional time
            self.parent.after(int((self.laser_duration_s+6.6)*1000),  self.turnLaserOff)

        else:
            self.turnLaserOn(sleep=False)
            time.sleep(-self.laser_wait_s)
            # Now start transient measurement
            self.keithley.write('script.anonymous.run()')
            print('Measurement in progress...')
        
            # wait here should be in ms
            # Takes about 6.6 s for 473 laser to start, so wait that additional time
            self.parent.after(int((self.laser_duration_s+6.6+self.laser_wait_s)*1000),  self.turnLaserOff)
        
        # Wait 'duration_s' + some fudge time to let test finish
        if not self.justStarted:
            self.onTime=time.time() - self.startTime
        else:
            self.justStarted=False
        self.startTime=time.time()-self.onTime
        file_modifier='_V='+str(self.tspInputDict['voltage_level']) + '_time=' + '{:.1f}'.format(self.onTime/60)+'min'
        header='Time (s),Current (A)'
        self.parent.after(int((self.tspInputDict['duration_s']+3)*1000),self.readTransientBuffer,file_modifier,header)
        self.parent.after(int(self.interval * 60 * 1000),  self.repeatCurrentTransient)
        
    def currentTransient(self,tspInputDict,laser_on_time,laser_wait):
        # interval_s,duration_s,
        # voltage,voltage_range,current_limit,current_range,
        # laser_on_time,laser_wait
        # Typical values:
        # interval_s = 0.05
        # duration_s = 10
        # current_limit = 0.04
        # current_range = factors of 10 from 100e-12 to 1
        # Load tsp
        # tspInputDict = {
                    # 'voltage_level':voltage,
                    # 'current_limit':current_limit, # in A
                    # 'current_range':current_range,
                    # 'voltage_range':voltage_range,
                    # 'interval_s':interval_s,
                    # 'duration_s':duration_s,
                    # }
        tsp_file = 'current_transient.tsp'
        self.loadTSP(tsp_file,tspInputDict)
        # Turn laser on, wait 'laser_wait' seconds, hold 'laser_on_time' seconds
        # If laser_wait is positive, start transient before turning on laser
        # If laser_wait is negative, do the opposite
        if laser_wait>=0:
            # Now start transient measurement
            self.keithley.write('script.anonymous.run()')
            print('Measurement in progress...')
            time.sleep(laser_wait)
            self.turnLaserOn(sleep=False)
            # wait here should be in ms
            # Takes about 6.6 s for 473 laser to start, so wait that additional time
            self.parent.after(int((laser_on_time+6.6)*1000),  self.turnLaserOff)

        else:
            self.turnLaserOn(sleep=False)
            time.sleep(-laser_wait)
            # Now start transient measurement
            self.keithley.write('script.anonymous.run()')
            print('Measurement in progress...')
        
            # wait here should be in ms
            # Takes about 6.6 s for 473 laser to start, so wait that additional time
            self.parent.after(int((laser_on_time+6.6+laser_wait)*1000),  self.turnLaserOff)
        
        # Wait 'duration_s' + some fudge time to let test finish
        file_modifier='_V='+str(tspInputDict['voltage_level'])
        header='Time (s),Current (A)'
        self.parent.after(int((tspInputDict['duration_s']+3)*1000),self.readTransientBuffer,file_modifier,header)
    def readTransientBuffer(self,file_modifier,header):
        # Read buffer
        timestamps = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.timestamps)').split(',')]
        currents = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)').split(',')]
        # Write file
        file = os.path.join(self.savepath,
                    self.filename+file_modifier+'.csv')

        with open(file, 'a') as f:
            f.write(header+'\n')
            for i in range(0,len(currents)):
                line = str(timestamps[i]) + ',' + str(currents[i])
                f.write(line+'\n')
        #self.parent.destroy()
                
    def voltageSweep(self,startV,stopV,stepV,nplc):
        ##-- USER INPUT
        ##local numSweepPts = 81
        ##local LEDstartV = 0
        ##local LEDstopV = 8
        ##local LED_current_limit = 0.1
        ##local photodector_current_limit = 0.1
        ##local NPLC = 10
        ##-- END USER INPUT
        tspInputDict = {'numSweepPts':int((stopV-startV)/stepV)+1,
                        'LEDstartV':startV,
                        'LEDstopV':stopV,
                        'LED_current_limit':0.04,
                        'photodector_current_limit':0.1,
                        'NPLC':nplc}
        
        tsp_file = 'oled_vsweep.tsp'
        self.loadTSP(tsp_file,tspInputDict)
        self.keithley.write('script.anonymous.run()')
        print('Measurement in progress...')
        #self.keithley.wait_for_srq() # This only works if plugged into GPIB
        # Calculate approximate sweep time and multiply by 2, to be safe
        sleepTime = tspInputDict['numSweepPts'] * nplc / 60 * 2
        if sleepTime < 3:
            sleepTime=3
        time.sleep(sleepTime)
        voltage,current,EL = self.readBuffer()
        #print(voltage)
        #print(current)
        #print(EL)
        self.turnCurrentOff()
        
        
        # Write file
        # header='# Voltage (V),Current (A),Photo Current (I)'
        # EQEfile = ('EQE_EL=' + '{:.2f}'.format(self.ELfraction*100) + '%_' + 
                   # '{:.2f}'.format(self.onTime/3600.0) + 'hr_'+
                   # self.filename + '.csv')

        # with open(EQEfile, 'a') as f:
            # f.write(header+'\n')
            # for i in range(0,len(current)):
                # line = str(voltage[i]) + ',' + str(current[i]) + ',' + str(EL[i]) + ',' + str(relativeEQE[i])
                # f.write(line+'\n')
        
        print('EQE measurement done')
        
        # re-initialize keithley
        self.initializeKeithley(self.keithley)
        return voltage,current,EL
    def write_eqe_file(self,voltage,current,EL):
        # Write file in EQE subdirectory
        self.eqe_dir = os.path.join(self.savepath,'EQE')
        if not os.path.isdir(self.eqe_dir):
            os.mkdir(self.eqe_dir)
        relativeEQE= ([0]+[(EL[i]-EL[0])/current[i] for i in range(1,len(current))])
        header='# Voltage (V),Current (A),Photo Current (I)'
        EQEfile = os.path.join(self.eqe_dir,
                   ('EQE_EL=' + '{:.2f}'.format(self.ELfraction*100) + '%_' + 
                   '{:.2f}'.format(self.onTime/3600.0) + 'hr_'+ self.baseString +
                   self.filename + '.csv')
                   )

        with open(EQEfile, 'a') as f:
            f.write(header+'\n')
            #print(len)
            for i in range(0,len(current)):
                line = str(voltage[i]) + ',' + str(current[i]) + ',' + str(EL[i]) + ',' + str(relativeEQE[i])
                f.write(line+'\n')
    def write_file_sync_sweep(self,times,V,I,EL,PL_avg,PL_std,during_deg=False):
        # Write file for synchronized lock-in and keithley sweep
        header=('# Time (s),Voltage (V),Current (A),Photocurrent (I),'
               +'PL avg (mV), PL std (mV)')
        baseString = datetime.datetime.now().strftime("%y%m%d") + "_"
        # Make lockin sweep subdirectory, if it doesn't already exist
        if during_deg:
            self.lockin_sweep_dir = os.path.join(self.savepath,'lockin_sweeps')
            if not os.path.isdir(self.lockin_sweep_dir):
                os.mkdir(self.lockin_sweep_dir)
            lockin_file = os.path.join(self.lockin_sweep_dir,
                       ('lockinsweep_EL=' + '{:.2f}'.format(self.ELfraction*100) + '%_' + 
                       '{:.2f}'.format(self.onTime/3600.0) + 'hr_'+ baseString +
                       self.filename + '.csv')
                       )
        else:
            lockin_file = os.path.join(self.savepath,baseString + self.filename + ".csv")
        with open(lockin_file, 'a') as f:
            f.write(header+'\n')
            for i in range(0,len(times)):
                line = ''.join(str(i)+',' for i in 
                               [times[i],V[i],I[i],EL[i],PL_avg[i],PL_std[i]])
                f.write(line[:-1]+'\n')
    def write_file_lockin_scan(self,time,data,during_deg = False):
        # Write file for synchronized lock-in and keithley sweep
        header=('# Time (s),PL (mV)')
        baseString = datetime.datetime.now().strftime("%y%m%d") + "_"
        # Make lockin sweep subdirectory, if it doesn't already exist
        if during_deg:
            self.lockin_sweep_dir = os.path.join(self.savepath,'lockin_sweeps')
            if not os.path.isdir(self.lockin_sweep_dir):
                os.mkdir(self.lockin_sweep_dir)
            lockin_file = os.path.join(self.lockin_sweep_dir,
                       ('lockinsweep_EL=' + '{:.2f}'.format(self.ELfraction*100) + '%_' + 
                       '{:.2f}'.format(self.onTime/3600.0) + 'hr_'+ baseString +
                       self.filename + "_full-lockin-data.csv")
                       )
        else:
            lockin_file = os.path.join(self.savepath,baseString + self.filename + "_full-lockin-data.csv")
        with open(lockin_file, 'a') as f:
            f.write(header+'\n')
            for i in range(0,len(time)):
                line = ''.join(str(i)+',' for i in 
                               [time[i],data[i]])
                f.write(line[:-1]+'\n')
    def init_and_run_fast_lockin_sweep(self,stopV):
        # Set lock-in settings
        # These are written with indices counting from 0
        for key,value in self.string_vars.items():
            if key in self.lockinSettingsOptions.keys():
                self.lockin.write(key + ' ' + 
                                  str(self.lockinSettingsOptions[key].index(value.get())))
        self.NPLC = float(self.string_vars['nplc'].get())
        self.startV = float(self.string_vars['voltage_start'].get())
        self.stopV = stopV
        self.stepV = float(self.string_vars['voltage_step'].get())
        self.delay = float(self.string_vars['delay'].get())
        #self.scan_rate = int(self.string_vars['srat'].get())
        self.fast_lockin_sweep(during_deg=True)
        # re-initialize keithley
        self.initializeKeithley(self.keithley)
    def init_and_run_slow_lockin_sweep(self,stopV):
        for key,value in self.string_vars.items():
            if key in self.lockinSettingsOptions.keys():
                self.lockin.write(key + ' ' + 
                                  str(self.lockinSettingsOptions[key].index(value.get())))
        self.NPLC = float(self.string_vars['nplc'].get())
        self.startV = float(self.string_vars['voltage_start'].get())
        self.stepV = float(self.string_vars['voltage_step'].get())
        self.voltages = np.arange(self.startV,stopV+0.01,self.stepV)
        self.lockinSoak = float(self.string_vars['lockinSoak'].get())
        self.readingCount = int(self.string_vars['readingCount'].get())
        self.lockinSweep(during_deg=True)
        # re-initialize keithley
        self.initializeKeithley(self.keithley)
    def lockin_lifetime_sweeps(self):
        # If test has been turned off, don't call function again
        if not self.test_running_bool:
            return
        # If test just started, initialize EQE and turn current on
        if self.continue_test_bool and self.justStarted:
            self.turnCurrentOn(self.current)
            self.startTime=time.time()-self.onTime
            self.justStarted = False
        if self.justStarted:
            self.turnCurrentOn(self.current)
            self.startTime=time.time()-self.onTime
            time.sleep(1)
            EL,EL_err = self.keithleyDiodeRead(self.keithley)
            self.firstEL = EL
            V = self.readVoltage()
            self.turnCurrentOff()
            self.onTime = time.time() - self.startTime
            self.justStarted = False
            # Initialize EQE
            self.ELfraction = 1
            self.lastEQE=self.ELfraction
            V_eqe,I_eqe,EL_eqe = self.voltageSweep(0,V+0.5,self.stepV,10)#start,stop,step,nplc
            self.write_eqe_file(V_eqe,I_eqe,EL_eqe)
            # Run lock-in sweep
            if self.fast_sweep_bool:
                self.init_and_run_fast_lockin_sweep(V+0.2)
            else:
                self.init_and_run_slow_lockin_sweep(V+0.2)
            # Turn current back on and start timer
            self.turnCurrentOn(self.current)
            self.startTime=time.time()-self.onTime
        # For the rest of the test, record the onTime, EL, and V. Check if EQE is needed
        else:
            self.onTime = time.time() - self.startTime
            EL,EL_err = self.keithleyDiodeRead(self.keithley)
            self.ELfraction = EL / self.firstEL
            V = self.readVoltage()
            # Take EQE scan and lock-in PL sweep
            if ( (self.lastEQE-self.ELfraction) > self.stepEQE ):
                print(self.ELfraction)
                self.turnCurrentOff()
                self.lastEQE=self.ELfraction
                V_eqe,I_eqe,EL_eqe = self.voltageSweep(0,V+0.5,self.stepV,10)#start,stop,step,nplc
                self.write_eqe_file(V_eqe,I_eqe,EL_eqe)
                # Run lock-in sweep
                if self.fast_sweep_bool:
                    self.init_and_run_fast_lockin_sweep(V+0.2)
                else:
                    self.init_and_run_slow_lockin_sweep(V+0.2)
                # Turn current back on and start timer
                self.turnCurrentOn(self.current)
                self.startTime=time.time()-self.onTime
        # Write line
        self.write_line_lifetime_sweeps(EL,V)
        # Call again in self.interval minutes unless below auto-stop level
        if self.ELfraction < self.autostop:
            self.turnLaserOff()
            self.turnCurrentOff()
            print('test stopped at ' + str(self.ELfraction))
        else:
            # In first hour, measure every 15 s
            if self.onTime < 3601:
                self.parent.after(int(0.25 * 60 * 1000),  self.lockin_lifetime_sweeps)
            else:
                self.parent.after(int(2 * 60 * 1000),  self.lockin_lifetime_sweeps)
                
    def lockin_lifetime(self):
        # If test has been turned off, don't call function again
        if not self.test_running_bool:
            return
        # EL_1 and V_1 are before turning current off and measuring PL
        # EL_2 and V_2 are right after turning current back on
        # PL is with current off, right after turning current off
        # PL_cond is after conditioning device at specified user conditions
        #stopV = 7
        if not self.justStarted:
            self.onTime = time.time() - self.startTime
            EL_1,EL_1_err = self.keithleyDiodeRead(self.keithley)
            self.ELfraction = EL_1 / self.firstEL
            V_1 = self.readVoltage()
            self.turnCurrentOff()
            # Take EQE scan
            if ( (self.lastEQE-self.ELfraction) > self.stepEQE ) and self.take_eqe_bool:
                self.lastEQE=self.ELfraction
                V_eqe,I_eqe,EL_eqe = self.voltageSweep(0,V_1,self.stepV,self.NPLC)#start,stop,step,nplc
                self.write_eqe_file(V_eqe,I_eqe,EL_eqe)
        else:
            self.turnCurrentOn(self.current)
            time.sleep(1)
            EL_1,EL_1_err = self.keithleyDiodeRead(self.keithley)
            self.firstEL = EL_1
            V_1 = self.readVoltage()
            self.turnCurrentOff()
            self.justStarted = False
            # Initialize EQE
            self.ELfraction = 1
            self.lastEQE = 2
            if ( (self.lastEQE-self.ELfraction) > self.stepEQE ) and self.take_eqe_bool:
                self.lastEQE=self.ELfraction
                V_eqe,I_eqe,EL_eqe = self.voltageSweep(0,V_1,self.stepV,self.NPLC)#start,stop,step,nplc
                self.write_eqe_file(V_eqe,I_eqe,EL_eqe)
        
        self.turnLaserOn()
        PL,PL_err = self.lockinRead()
        print(PL)
        laser_1,laser_1_err = self.keithleyDiodeRead(self.keithley_laser)
        self.turnLaserOff()
        # Condition device at reverse bias and measure PL again
        self.turnVoltageOn(self.reverseV)
        time.sleep(self.condition_time)
        self.turnVoltageOff()
        self.turnLaserOn()
        PL_cond,PL_cond_err = self.lockinRead()
        
        # Measure PL at low current
        if self.low_current>0:
            self.turnCurrentOn(self.low_current)
            time.sleep(1)
            PL_lowJ,PL_lowJ_err = self.lockinRead()
            laser_3,laser_3_err = self.keithleyDiodeRead(self.keithley_laser)
            print(PL_lowJ)
        
        # Measure PL with current on
        self.turnCurrentOn(self.current)
        self.startTime=time.time()-self.onTime
        time.sleep(1)
        PL_J,PL_J_err = self.lockinRead()
        laser_2,laser_2_err = self.keithleyDiodeRead(self.keithley_laser)
        print(PL_J)
        
        # Measure EL
        self.turnLaserOff()
        EL_2,EL_2_err = self.keithleyDiodeRead(self.keithley)
        print(EL_2) 
        V_2 = self.readVoltage()
        
        # Write line
        #self.write_line_lifetime(EL_1,V_1,EL_2,V_2,PL_J,PL_J_err,PL,PL_err,PL_cond,PL_cond_err)
        self.write_line_lifetime_laser(EL_1,V_1,EL_2,V_2,PL_J,PL_J_err,PL,PL_err,PL_cond,PL_cond_err,
                                       laser_1,laser_1_err,laser_2,laser_2_err,PL_lowJ,PL_lowJ_err,laser_3,laser_3_err)
        # Call again in self.interval minutes unless below auto-stop level
        if self.ELfraction < self.autostop:
            self.turnLaserOff()
            self.turnCurrentOff()
            print('test stopped at ' + str(self.ELfraction))
        else:
            # In first hour, measure twice as often
            if self.onTime < 3601:
                self.parent.after(int(self.interval * 60 * 1000 * 0.5),  self.lockin_lifetime)
            else:
                self.parent.after(int(self.interval * 60 * 1000),  self.lockin_lifetime)
            
def main(): 
    root = tk.Tk()
    app = VoltageController(root)
    root.mainloop()
    #app.keithley.close()
    app.arduino.close()

if __name__ == '__main__':
    main()  