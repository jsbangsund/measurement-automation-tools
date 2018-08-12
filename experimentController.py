# imports
import visa
import numpy as np
import os
import csv
import time
import datetime
import tkinter as tk
#from tkinter import *
from tkinter.filedialog import askopenfilename, askdirectory
from tkinter.ttk import Frame, Button, Style,Treeview, Scrollbar, Checkbutton
from functools import partial
# This program sweeps current on a device and measures
# lock-in PL
# TODO add re-connect to instrument button?
# TODO make writeLine and initializeFiles more general?
class PLController(Frame):
    def __init__(self,parent):
        #### USER DEFINED
        self.basefilename = 'OD=1.5_lam=405nm_lockinVSweep_mCBP'
        self.savepath = 'lockinSweeps\\'
        self.complianceV = 20
        self.interval = 10 # in minutes
        self.readingCount = 50 # Number of lock-in readings to average
        self.keithleyReadingCount = 10
        # Reverse bias conditioning:
        self.reverseV =  -2
        self.condition_time = 10 # hold time for voltage in seconds

        # Lock-in settings (see more details and options below):
        self.default_lockin_settings = {
        'sens': '20mV', # Sensitivity range
        'oflt': '100ms', # Time constant
        'icpl' : 'AC',   # Input coupling
        'isrc' : 'A-B',  # input type
        'ignd' : 'Float', # Choose Float if signal is grounded and vice versa
        'ofsl' : '24db/oct', # low-pass filter slope
        'ilin' : 'None' # Notch filters for input power line
        }
        self.lockinSoak = 1 # in seconds, should be 10x timeConstant

        # To measure PD current straight from keithley:
        self.test_type = 'transientI' #'transientI','transientV','keithleySweep','lockinSweep'
        #### End user defined parameters


        #############################################################################
        # Lock-in settings options
        # Read the manual for more info:
        # http://www.thinksrs.com/downloads/PDFs/Manuals/SR810m.pdf

        # Note on input coupling
        # The AC coupling applies a high pass filter to remove signal
        # above 160 mHz (0.16 Hz) and attenuates signals
        # at lower frequencies. AC coupling should be used
        # at frequencies above 160 mHz whenever possible.
        # At lower frequencies, DC coupling is required.

        # Notch filters at 60 Hz (line frequency), 120 Hz, Both, or none

        # The index of a given setting within a list is passed to the lock-in

        self.lockinSettingsOptions = {
        'sens':['2nV', '5nV', '10nV', '20nV','50nV', '100nV', '200nV', '500nV',
               '1uV','2uV', '5uV', '10uV', '20uV','50uV', '100uV', '200uV', '500uV',
               '1mV','2mV', '5mV', '10mV', '20mV','50mV', '100mV', '200mV', '500mV', '1V'],
        'oflt': ['10us', '30us', '100us', '300us',
                '1ms', '3ms','10ms', '30ms', '100ms', '300ms',
                '1s', '3s','10s', '30s', '100s', '300s',
                '1ks', '3ks','10ks', '30ks'],
        'icpl' : ['AC','DC'] ,   # Input coupling
        'isrc' : ['A', 'A-B', 'I, 1 MOhm', 'I, 100 MOhm'] ,  # input type
        'ignd' : ['Float','Ground'],# Choose Float if signal is grounded and vice versa
        'ofsl' : ['6db/oct','12db/oct','18db/oct','24db/oct'], # low-pass filter slope
        'ilin' : ['None','Line','2xLine','Both'] # Notch filters for input power line
        }
        #############################################################################

        Frame.__init__(self, parent)
        self.parent = parent
        self.connect_to_instruments()
        self.configure_gui()

    def connect_to_instruments(self):
        # Open instruments
        self.rm = visa.ResourceManager()
        self.resources = self.rm.list_resources()
        # Connect to keithley and lock-in and laser
        # Easiest way to identify keithley's is by 7 digit SN on back panel
        keithley2636 = '#######'
        keithley2604 = '#######'
        laserDev = '3'
        lockinAddress = 'GPIB0::8::INSTR'
        for resource in self.resources:
            if keithley2636 in resource:
                self.keithley = self.rm.open_resource(resource)
                self.initializeKeithley()
                print('keithley connected')
            if lockinAddress in resource:
                self.lockin = self.rm.open_resource(resource, write_termination = '\n')
                #Tell the lock-in to communicate via GPIB
                self.lockin.write('outx 1')
                print('lock-in connected')
            if ('ASRL' + laserDev + '::INSTR') in resource:
                self.obis = self.rm.open_resource(resource)
                self.obis.write('syst1:comm:hand off')
                self.turnLaserOff()
                print('laser connected')

    def configure_gui(self):
        # Master Window
        self.parent.title("Experiment Controller")
        self.style = Style()
        self.style.theme_use("default")

        # Test Mode Frame
        frame_mode=Frame(self)
        frame_mode.pack()
        self.s_mode=tk.StringVar()
        self.test_modes=['keithleySweep','lockinSweep','transientI','transientV']
        self.rb_tests=[]
        for idx,test in enumerate(self.test_modes):
            self.rb_tests.append(tk.Radiobutton(frame_mode,
                text=test,variable=self.s_mode,value=test,command=self.modeSelect))
            self.rb_tests[idx].pack(side=tk.LEFT)

        # Laser Frame
        frame_laser=Frame(self)
        frame_laser.pack()

        tk.Label(frame_laser,text="Laser Signal").pack(side=tk.LEFT)
        self.b_LaserTest=Button(frame_laser,text="Off", command=self.laserOffClick)
        self.b_LaserTest.pack(side=tk.RIGHT)
        self.b_LaserTest=Button(frame_laser,text="On", command=self.laserOnClick)
        self.b_LaserTest.pack(side=tk.RIGHT)
        self.l_laserStatus=tk.Label(frame_laser,text="Laser Is Off",bg="red")
        self.l_laserStatus.pack(padx=2, pady=2,side=tk.RIGHT)

        # Initialize inputs frame (filled in when radio button is selected)
        self.frame_inputs = Frame(self)
        self.frame_inputs.pack()

        # Start test
        frame_buttons=Frame(self)
        frame_buttons.pack()
        Button(frame_buttons,text="Start Test",
                command=self.startTestClick).grid(row=0,column=0,sticky=tk.W,padx=1, pady=1)
        # Stop test
        tk.Button(frame_buttons,text="Stop Test", bg="red",
                command=self.stopTestClick).grid(row=0,column=1,sticky=tk.W,padx=1, pady=1)
        # Style Configuration
        Style().configure("defaultState.TButton", foreground='black', background='light grey')
        Style().configure("onState.TButton", foreground='black', background='red')
        Style().map("onState.TButton",
                    background=[('disabled', 'grey'),
                                ('pressed', 'red3'),
                                ('active', 'red2')])

        self.pack(fill=tk.BOTH, expand=1)
    def modeSelect(self):
        if self.s_mode.get()=='transientI':
            self.userInputs = { 'duration_s':
                                    {'label':"Test Duration (s):",
                                    'default_val':"240",
                                    'type':'Entry'},
                                'interval_s':
                                    {'label':"Meas. Interval (s):",
                                    'default_val':"0.05",
                                    'type':'Entry'},
                                'laser_duration_s':
                                    {'label':"Laser Duration (s):",
                                    'default_val':"30",
                                    'type':'Entry'},
                                'laser_wait_s':
                                    {'label':"Laser Wait (s):",
                                    'default_val':"30",
                                    'type':'Entry'},
                                'voltage_level':
                                    {'label':"Voltage:",
                                    'default_val':"10",
                                    'type':'Entry'},
                                'voltage_range':
                                    {'label':"Voltage Range:",
                                    'default_val':"20",
                                    'type':'Entry'},
                                'current_range':
                                    {'label':"Current Range:",
                                    'default_val':"10e-3",
                                    'type':'Entry'},
                                'current_limit':
                                    {'label':"Current Limit:",
                                    'default_val':"0.04",
                                    'type':'Entry'}}

        elif self.s_mode.get()=='transientV':
            self.userInputs = { 'duration_s':
                                    {'label':"Test Duration (s):",
                                    'default_val':"240",
                                    'type':'Entry'},
                                'interval_s':
                                    {'label':"Meas. Interval (s):",
                                    'default_val':"0.05",
                                    'type':'Entry'},
                                'laser_duration_s':
                                    {'label':"Laser Duration (s):",
                                    'default_val':"30",
                                    'type':'Entry'},
                                'laser_wait_s':
                                    {'label':"Laser Wait (s):",
                                    'default_val':"30",
                                    'type':'Entry'},
                                'voltage_range':
                                    {'label':"Voltage Range:",
                                    'default_val':"20",
                                    'type':'Entry'},
                                'voltage_limit':
                                    {'label':"Voltage Limit:",
                                    'default_val':"20",
                                    'type':'Entry'},
                                'current_range':
                                    {'label':"Current Range:",
                                    'default_val':"10e-3",
                                    'type':'Entry'},
                                'current_level':
                                    {'label':"Current Level:",
                                    'default_val':"1e-3",
                                    'type':'Entry'}}

        elif self.s_mode.get()=='keithleySweep':
            self.userInputs = {'voltage_start':
                                    {'label':"Start Voltage:",
                                    'default_val':"0",
                                    'type':'Entry'},
                                'voltage_stop':
                                    {'label':"Stop Voltage:",
                                     'default_val':"10",
                                     'type':'Entry'},
                                'voltage_step':
                                    {'label':"Voltage Step:",
                                    'default_val':"0.5",
                                    'type':'Entry'},
                                'NPLC':
                                    {'label':"NPLC:",
                                    'default_val':"10",
                                    'type':'Entry'}}

        elif self.s_mode.get()=='lockinSweep':
            self.userInputs =  {'voltage_start':
                                    {'label':"Start Voltage:",
                                    'default_val':"0",
                                    'type':'Entry'},
                                'voltage_stop':
                                    {'label':"Stop Voltage:",
                                     'default_val':"10",
                                     'type':'Entry'},
                                'voltage_step':
                                    {'label':"Voltage Step:",
                                    'default_val':"0.5",
                                    'type':'Entry'},
                                'readingCount':
                                    {'label':"Lock-in Reading Count:",
                                    'default_val':str(self.readingCount),
                                    'type':'Entry'},
                                'lockinSoak':
                                    {'label':"Lock-in Soak (10x Tau in sec):",
                                    'default_val':str(self.lockinSoak),
                                    'type':'Entry'},
                                'sens':
                                    {'label':"Sensitivity:",
                                    'default_val':self.default_lockin_settings['sens'],#"20mV"
                                    'type':'OptionMenu'},
                                'oflt':
                                    {'label':"Time Constant:",
                                    'default_val':self.default_lockin_settings['oflt'],#"20ms"
                                    'type':'OptionMenu'},
                                'icpl':
                                    {'label':"Input Coupling:",
                                    'default_val':self.default_lockin_settings['icpl'],#"AC"
                                    'type':'OptionMenu'},
                                'isrc':
                                    {'label':"Input Type:",
                                    'default_val':self.default_lockin_settings['isrc'],#"A"
                                    'type':'OptionMenu'},
                                'ignd':
                                    {'label':"Grounding:",
                                    'default_val':self.default_lockin_settings['ignd'],#"Ground",
                                    'type':'OptionMenu'},
                                'ofsl':
                                    {'label':"Filter Slope:",
                                    'default_val':self.default_lockin_settings['ofsl'],#"24db/oct",
                                    'type':'OptionMenu'},
                                'ilin':
                                    {'label':"Notch Filter:",
                                    'default_val':self.default_lockin_settings['ilin'],#"None",
                                    'type':'OptionMenu'}}
        # Destroy previous elements of frame (if any)
        for widget in self.frame_inputs.winfo_children():
            widget.destroy()
        self.string_vars={}
        self.entries = ['']*len(self.userInputs)
        row_idx=0
        for key,input_dict in self.userInputs.items():

            tk.Label(self.frame_inputs,text=input_dict['label']).grid(row=row_idx,column=0)
            self.string_vars[key]=tk.StringVar()
            self.string_vars[key].set(input_dict['default_val'])
            if input_dict['type']=='Entry':
                self.entries[row_idx]=tk.Entry(self.frame_inputs,
                                        textvariable=self.string_vars[key])
            # If this is a lock-in test and an option menu is selected,
            # populate the options via lockinSettingsOptions
            # and call command to write setting
            elif input_dict['type']=='OptionMenu' and 'lockin' in self.s_mode.get():
                self.entries[row_idx]=tk.OptionMenu(self.frame_inputs,
                                        self.string_vars[key],
                                        *self.lockinSettingsOptions[key])
                                        # This isn't working because it just takes the last value
                                        #command=lambda _: self.lockinSettingsClick(input_dict['key']))
            elif input_dict['type']=='OptionMenu':
                self.entries[row_idx]=tk.OptionMenu(self.frame_inputs,
                                        self.string_vars[key],
                                        *input_dict['options'])
            elif input_dict['type']=='Checkbutton':
                self.string_vars[key]=tk.BooleanVar()
                self.string_vars[key].set(input_dict['default_val'])
                self.entries[row_idx]=tk.Checkbutton(
                                self.frame_inputs,
                                variable=self.string_vars[key],
                                onvalue=True,offvalue=False)
            self.entries[row_idx].grid(row=row_idx,column=1)
            row_idx+=1
        # Add savepath and filename entries
        self.s_savepath = tk.StringVar()
        self.s_savepath.set(self.savepath)
        tk.Label(self.frame_inputs,text="Save Path").grid(row=len(self.userInputs),column=0)
        tk.Entry(self.frame_inputs,textvariable=self.s_savepath,width=40).grid(row=len(self.userInputs),
                                                                    column=1,sticky=tk.W)
        self.s_filename = tk.StringVar()
        self.s_filename.set(self.basefilename)
        tk.Label(self.frame_inputs,text="Filename").grid(row=len(self.userInputs)+1,column=0)
        tk.Entry(self.frame_inputs,textvariable=self.s_filename,width=40).grid(row=len(self.userInputs)+1,
                                                                    column=1,sticky=tk.W)


    def startTestClick(self):
        self.filename=self.s_filename.get()
        self.savepath=self.s_savepath.get()
        if self.s_mode.get()=='transientI':
            tsp_keys = ['voltage_level','voltage_range','current_limit',
                'current_range','interval_s','duration_s']
            tspInputDict = {tsp_key: float(self.string_vars[tsp_key].get()) for tsp_key in tsp_keys}
            self.currentTransient(tspInputDict,
                        float(self.string_vars['laser_duration_s'].get()),
                        float(self.string_vars['laser_wait_s'].get()))
        elif self.s_mode.get()=='transientV':
            tsp_keys = ['voltage_limit','voltage_range','current_level',
                'current_range','interval_s','duration_s']
            tspInputDict = {tsp_key: float(self.string_vars[tsp_key].get()) for tsp_key in tsp_keys}
            self.voltageTransient(tspInputDict,
                        float(self.string_vars['laser_duration_s'].get()),
                        float(self.string_vars['laser_wait_s'].get()))
        elif self.s_mode.get()=='keithleySweep':
            self.voltages = np.arange(float(self.string_vars['voltage_start'].get()),
                                      float(self.string_vars['voltage_stop'].get()),
                                      float(self.string_vars['voltage_step'].get()))
            self.NPLC = float(self.string_vars['NPLC'].get())
            self.initializeFiles()
            self.keithleySweepTest()
        elif self.s_mode.get()=='lockinSweep':
            self.voltages = np.arange(float(self.string_vars['voltage_start'].get()),
                                      float(self.string_vars['voltage_stop'].get()),
                                      float(self.string_vars['voltage_step'].get()))
            # Set lock-in settings
            # These are written with indices counting from 0
            for key,value in self.string_vars.items():
                if key in self.lockinSettingsOptions.keys():
                    self.lockin.write(key + ' ' +
                                      str(self.lockinSettingsOptions[key].index(value.get())))
            self.lockinSoak = float(self.string_vars['lockinSoak'].get())
            self.readingCount = int(self.string_vars['readingCount'].get())
            self.initializeFiles()
            self.lockinSweep()

    def stopTestClick(self):
        # Turn off test running bool:
        self.test_running_bool = False
        # Turn off laser
        self.turnLaserOff()
        # Turn off current
        self.turnCurrentOff()
    def lockinSettingsClick(self,key):
        write_command = (key + ' ' +
            str(self.lockinSettingsOptions[key].index(self.string_vars[key].get())))
        print(write_command)
        self.lockin.write(write_command)

    def laserOnClick(self):
        self.turnLaserOn(sleep=False)
        self.l_laserStatus.configure(bg="green",text="Laser is On")

    def laserOffClick(self):
        self.turnLaserOff()
        self.l_laserStatus.configure(bg="red",text="Laser is Off")

    def turnLaserOn(self,sleep=True):
        print('laser turned on')
        self.obis.write('sour1:am:stat on')
        if sleep:
            for z in range(10):
                time.sleep(1)

    def turnLaserOff(self):
        print('laser turned off')
        self.obis.write('sour1:am:stat off')

    def initializeKeithley(self):
        self.keithley.write('reset()')
        self.keithley.timeout = 4000 # ms
        self.keithley.write('errorqueue.clear()')
        ch = 'a'
        self.keithley.write( 'smu'+ch+'.reset()')
        self.keithley.write( 'smu'+ch+'.measure.count=1')
        self.keithley.write( 'smu'+ch+'.measure.nplc=1')
        self.keithley.write( 'smu'+ch+'.nvbuffer1.appendmode=0')
        self.keithley.write( 'smu'+ch+'.nvbuffer1.clear()')
        self.keithley.write( 'smu'+ch+'.source.func=0') # 0 is output_DCAMPS, 1 is output_DCVOLTS
        self.keithley.write( 'smu'+ch+'.source.limitv='+str(self.complianceV))
        self.keithley.write( 'smu'+ch+'.source.levelv=0')
        self.keithley.write( 'smu'+ch+'.source.output=0')
        self.keithley.write( 'smu'+ch+'.measure.autorangev=1')
        ch = 'b'
        self.keithley.write( 'smu'+ch+'.reset()')
        self.keithley.write( 'smu'+ch+'.measure.count=10')
        self.keithley.write( 'smu'+ch+'.measure.nplc=1')
        self.keithley.write( 'smu'+ch+'.nvbuffer1.appendmode=0')
        self.keithley.write( 'smu'+ch+'.nvbuffer1.clear()')
        self.keithley.write( 'smu'+ch+'.source.func=1') # 0 is output_DCAMPS, 1 is output_DCVOLTS
        self.keithley.write( 'smu'+ch+'.source.levelv=0')
        self.keithley.write( 'smu'+ch+'.measure.autorangei=1')
        self.keithley.write( 'smu'+ch+'.source.output=1')
        print('keithley initialized')

    def turnCurrentOn(self,I):
        print('current turned on')
        self.keithley.write( 'smua.source.leveli='+str(I))
        self.keithley.write( 'smua.source.output=1')

    def turnCurrentOff(self):
        print('current turned off')
        self.keithley.write( 'smua.source.output=0')

    def turnVoltageOn(self,V):
        print('voltage turned on')
        self.keithley.write( 'smua.source.func=1') # 0 is output_DCAMPS, 1 is output_DCVOLTS
        self.keithley.write( 'smua.source.levelv='+str(V))
        self.keithley.write( 'smua.source.output=1')

    def turnVoltageOff(self):
        print('voltage turned off')
        self.keithley.write( 'smua.source.levelv=0')
        self.keithley.write( 'smua.source.func=0') # 0 is output_DCAMPS, 1 is output_DCVOLTS
        self.keithley.write( 'smua.source.output=0')

    # reads the voltage from keithley of the specified device
    def readVoltage(self):
        return float(self.keithley.query('printnumber(smua.measure.v())'))

    def readCurrent(self):
        self.keithley.write( 'smua.measure.autorangei=1')
        return float(self.keithley.query('printnumber(smua.measure.i())'))

    # reads device photodiode signal measured by keithley from specified device
    def keithleyDiodeRead(self):
        holder = []
        for x in range(0,self.keithleyReadingCount):
            self.keithley.write('smub.nvbuffer1.clear()')
            self.keithley.write('smub.measure.i(smub.nvbuffer1)')
            sig = self.keithley.query('printbuffer(1,smub.nvbuffer1.n,smub.nvbuffer1)')
            sig=[float(v) for v in sig.split(',')]
            holder.append(sig)
        return np.mean(holder),np.std(holder)

    def lockinRead(self):
        # The sleep here is to wait ~10 time constants for the reading average to converge
        time.sleep(self.lockinSoak)
        holder = []
        # outp? i ---> X (i=1), Y (i=2), R (i=3) or q (i=4)
        for x in range(0,self.readingCount):
            holder.append(float(self.lockin.query('outp? 3')))
            time.sleep(0.1)
        current = np.mean(holder)
        stdev   = np.std(holder)
        return current,stdev

    def initializeFiles(self):
        self.baseString = datetime.datetime.now().strftime("%y%m%d") + "_"
        self.file = os.path.join(self.savepath,self.baseString + self.filename + ".csv")
        line1="J,EL,V,PL (J on),PL err (J on)\n"
        line2="amps,amps,volts,amps,amps\n"
        with open(self.file, 'a') as f:
            f.write(line1)
            f.write(line2)

        # Write settings file
        # Saves info about lock-in and other settings
        self.settings_dir = os.path.join(self.savepath,'Settings')
        if not os.path.isdir(self.settings_dir):
            os.mkdir(self.settings_dir)
        self.settings_file = os.path.join(self.settings_dir,self.baseString + self.filename + '_settings.csv')
        with open(self.settings_file, 'a') as f:
            f.write('Test Type:,'+self.s_mode.get()+'\n')
            # Write user-input settings
            for key,value in self.userInputs.items():
                f.write(key + ',' + str(self.string_vars[key].get()) + '\n')
            if 'lockin' in self.s_mode.get():
                f.write('Lock-in Reading Count,'+str(self.readingCount) + '\n')
                f.write('Lock-in Soak,'+str(self.lockinSoak) + '\n')
                try:
                    lockin_freq = self.lockin.query('freq?')
                except:
                    lockin_freq = 'error'
                f.write('Chopper Frequency,' + str(lockin_freq) + '\n')
            # Write other test settings
            try:
                lwave = self.obis.query('system:information:wavelength?')
                laser_snumber = self.obis.query('system:information:snumber?')
            except:
                lwave='error'
                laser_snumber = 'error'
            f.write('Laser wavelength (nm),'+str(lwave)+'\n')
            f.write('Laser SN,'+str(laser_snumber)+'\n')

    def writeLine(self,J,EL,V,PL_J,PL_J_err):
        #"date,On Time,EL,V,PL (J on),PL err (Jon),PL (J off), PL err (J off)\n"
        line = (str(J)+','+
                str(EL)+','+
                str(V)+','+
                str(PL_J)+','+
                str(PL_J_err)+','+'\n')
        with open(self.file, 'a') as f:
            f.write(line)

    def loadTSP(self, tsp,tspInputDict):
        '''Load an anonymous TSP script into the K2636 nonvolatile memory'''
        tsp_dir = '\\tsp\\' # Put all tsp scripts in this folder

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
        print('----------------------------------------')
        print ('Uploaded TSP script: ', tsp)

    def readBuffer(self):
        #'''Read specified buffer in keithley memory and return a pandas array'''
        #V = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)').split(',')]
        V = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer2.n, smua.nvbuffer2.readings)').split(',')]
        I = [float(x) for x in self.keithley.query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)').split(',')]
        EL = [float(x) for x in self.keithley.query('printbuffer(1, smub.nvbuffer1.n, smub.nvbuffer1.readings)').split(',')]
        return V,I,EL

    def lockinSweep(self):
        self.turnLaserOn()
        #PL_J,PL_J_err = self.lockinRead()
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
            PL_J,PL_J_err = self.lockinRead()
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

        # Write file
        #for idx in range(0,len(self.voltages)):
        #    self.writeLine(current[idx],0,voltage[idx],PL[idx],0)
        # Close down
        #self.parent.destroy()

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
            PL_J,PL_J_err = self.keithleyDiodeRead()
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
        # CLose down
        #self.parent.destroy()

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
        self.initializeKeithley()
        return voltage,current,EL
    def write_eqe_file(self,voltage,current,EL):
        # Write file in EQE subdirectory
        self.eqe_dir = os.path.join(self.savepath,'EQE_'+self.filename)
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

def main():
    root = tk.Tk()
    app = PLController(root)
    root.mainloop()
    app.obis.write('sour1:am:stat off') # turn off laser
    app.obis.close()
    app.lockin.close()
    app.keithley.close()
    #app.arduino.close()

if __name__ == '__main__':
    main()
