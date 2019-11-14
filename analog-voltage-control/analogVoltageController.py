# imports
import visa
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
# This app uses an arduino to output two analog voltage channels from 0 to ~3.3V
# These output voltages are used to control flow rate on mass flow controllers
class VoltageController(Frame):
    def __init__(self,parent):
        #### USER DEFINED
        self.arduinoAddress = 'COM5'
        self.window_title = "Mass Flow Control"
        self.channels = ["A","B"]
        self.V_calibration = {i:None for i in self.channels} # initialize correction factor
        self.show_keithley = True
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
        self.keithley.write('smua.measure.autorangei=1')
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
    
    
def main(): 
    root = tk.Tk()
    app = VoltageController(root)
    root.mainloop()
    #app.keithley.close()
    app.arduino.close()

if __name__ == '__main__':
    main()  