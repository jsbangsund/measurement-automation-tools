import seabreeze.spectrometers as sb
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
import seabreeze.backends

class spectrometer():
    def __init__(self):
        lib = seabreeze.backends.get_backend()
        devices = sb.list_devices()
        if not devices:
            raise ValueError('No spectrometer found')
        else:
            #Close the device first
            lib.device_close(devices[0])
            #this opens up the first spectrometer it finds
            #assuming we will only ever have one spectrometer
            self.spec = sb.Spectrometer(devices[0])

        self.intTime = 500 #milliseconds
        self.spec.integration_time_micros(self.intTime * 1e3)	
        print 'int time set'

        self.darkWaves=[]
        self.darkIntensities=[]
        self.waves=[]
        self.intensities=[]
        self.rawIntensities=[]
        print 'reading cal'
        self.readCalibration()
        print 'cal read'

    def takeSpectrum(self):
        self.waves = self.spec.wavelengths()
        
        self.rawIntensities = self.spec.intensities()
        if self.darkIntensities==[]:
            self.intensities=self.spec.intensities()
        else:
            self.intensities = (self.spec.intensities() - self.darkIntensities)*self.calibration
        #return waves,intensites

    def readCalibration(self):
        header_rows=9

        self.calibration = []
        f = open('HR4000 calibration 150910_OOIIrrad.cal', "rb")
# ignore rows    
        for x in xrange(header_rows): 
            f.next()
# read data        
        for line in f:       
            calibrationFactor = float(line)
            self.calibration.append(calibrationFactor)
        print self.calibration
        print np.array(self.calibration)
        self.calibration=np.array(self.calibration)
            
        
    def setAsDark(self):
        self.darkWaves = self.waves
        self.darkIntensities = self.rawIntensities
        
    def makePlot(self):

        fig, ax = plt.subplots()
        line1 = ax.plot(self.waves, self.intensities, '--', linewidth=2, label = 'label')
        plt.show()


print 'here'
sp=spectrometer()		
print 'here'
while 1:
	entry = raw_input('What to do? ("d" to store as dark, "s" to take spectrum)  ')
	if entry=='d':
		sp.takeSpectrum()
		sp.setAsDark()
		sp.makePlot()
	if entry=='s':
		sp.takeSpectrum()
		sp.makePlot()
