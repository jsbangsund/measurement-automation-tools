#!/home/ross/.anaconda3/bin/python
#coding:utf-8

"""
  Author:  Ross <peregrine.warren@physics.ox.ac.uk>
  Purpose: Simple' driver for Keithley 2636
  Created: 07/03/17
"""

import visa
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.style as style
import time

# import visa

# mysmu=visa.instrument('gpib0::26::instr')

# mysmu.write('reset()')
# mysmu.write('errorqueue.clear()')

# mysmu.write('loadandrunscript')
# mysmu.write('function DoMyThing(duration, frequency)')
# mysmu.write('beeper.beep(duration, frequency)')
# mysmu.write('end')
# mysmu.write('endscript')

# mysmu.write('DoMyThing(1, 800)')

# mysmu.close() 

########################################################################
class K2636():
	"""Class for Keithley control"""

	#----------------------------------------------------------------------
	def __init__(self, address='ASRL/dev/ttyUSB0', read_term='\n', baudrate=57600):
		"""Initial constructor"""
		try:
			rm = visa.ResourceManager('@py') #use py-visa backend
			self.makeConnection(rm, address, read_term, baudrate)
		except:
			raise ConnectionError()

	#----------------------------------------------------------------------
	def makeConnection (self, rm, address, read_term, baudrate):
		"""Make initial connection to instrument"""

		try:
			if 'ttyS' or 'ttyUSB' in str(address) :
				# Connection via SERIAL
				self.inst = rm.open_resource(address)
				self.inst.read_termination = str(read_term)
				self.inst.baud_rate = baudrate

			if 'GPIB' in str(address):
				# Connection via GPIB
				print ('GPIB not programmed yet. Please use serial')
				sys.exit()

		except:
			raise ConnectionError()
	#----------------------------------------------------------------------
	def closeConnection(self):
		'''Closes connection to keithley'''
		try:
			self.inst.close()
			#print ('Connection closed.')

		except(NameError):
			print('Can not close connection as connection was never open!')

		except(AttributeError):
			print('Can not close connection as connection was never open!')

	#----------------------------------------------------------------------
	def _write(self, m):
		'''Wrapper for the PyVisa write function'''
		assert type(m) == str
		self.inst.write(m)


	#----------------------------------------------------------------------
	def _read(self):
		'''Wrapper for the PyVisa read function'''
		r = self.inst.read()
		return r

	#----------------------------------------------------------------------
	def _query(self, s):
		'''Wrapper for the PyVisa query function'''
		r = self.inst.query(s)
		return r

	#----------------------------------------------------------------------
	def loadTSP(self, tsp):
		'''Load an anonymous TSP script into the K2636 nonvolatile memory'''
		tsp_dir = 'tsp/' # Put all tsp scripts in this folder

		self._write('loadscript')
		line_count = 1
		for line in open(str(tsp_dir + tsp), mode='r'):
			self._write(line)
			line_count += 1
		self._write('endscript')
		print('----------------------------------------')
		print ('Uploaded TSP script: ', tsp)

	#----------------------------------------------------------------------
	def runTSP(self):
		'''Run the anonymous TSP script currently loaded in the K2636 memory'''
		self._write('script.anonymous.run()')
		print('Measurement in progress...')

	#----------------------------------------------------------------------
	def readBuffer(self):
		'''Read specified buffer in keithley memory and return a pandas array'''
		vg = [float(x) for x in self._query('printbuffer(1, smub.nvbuffer1.n, smub.nvbuffer1.sourcevalues)').split(',')]
		ig = [float(x) for x in self._query('printbuffer(1, smub.nvbuffer1.n, smub.nvbuffer1.readings)').split(',')]
		vd = [float(x) for x in self._query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)').split(',')]
		c = [float(x) for x in self._query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)').split(',')]

		df = pd.DataFrame({'Gate Voltage [V]': vg, 'Channel Voltage [V]' : vd, 'Channel Current [A]': c, 'Gate Leakage [A]': ig})
		return df


	#----------------------------------------------------------------------
	def readBufferIV(self):
		'''Read specified buffer in keithley memory and return a pandas array'''
		vd = [float(x) for x in self._query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.sourcevalues)').split(',')]
		c = [float(x) for x in self._query('printbuffer(1, smua.nvbuffer1.n, smua.nvbuffer1.readings)').split(',')]
		df = pd.DataFrame({'Channel Voltage [V]' : vd, 'Channel Current [A]': c})
		return df
	#----------------------------------------------------------------------
	def DisplayMeasurement(self, sample):
		'''Show graphs of measurements'''
		try:
			style.use('ggplot')
			fig, ([ax1, ax2], [ax3, ax4]) = plt.subplots(2, 2, figsize=(20, 10), dpi= 80, facecolor='w', edgecolor='k')
			df1 = pd.read_csv(str(sample+'-iv-sweep.csv'),'\t')
			ax1.plot(df1['Channel Voltage [V]'], df1['Channel Current [A]'], '.')
			ax1.set_title('I-V sweep')
			ax1.set_xlabel('Channel Voltage [V]')
			ax1.set_ylabel('Channel Current [A]')

			df2 = pd.read_csv(str(sample+'-output.csv'),'\t')
			ax2.plot(df2['Channel Voltage [V]'], df2['Channel Current [A]'], '.')
			ax2.set_title('Output curves')
			ax2.set_xlabel('Channel Voltage [V]')
			ax2.set_ylabel('Channel Current [A]')

			df3 = pd.read_csv(str(sample+'-transfer.csv'),'\t')
			ax3.plot(df3['Gate Voltage [V]'], df3['Channel Current [A]'], '.')
			ax3.set_title('Transfer Curves')
			ax3.set_xlabel('Gate Voltage [V]')
			ax3.set_ylabel('Channel Current [A]')

			df4 = pd.read_csv(str(sample+'-transfer.csv'),'\t')
			ax4.plot(df4['Gate Voltage [V]'], df4['Gate Leakage [A]'], '.')
			ax4.set_title('Gate leakage current')
			ax4.set_xlabel('Gate Voltage [V]')
			ax4.set_ylabel('Gate Leakage [A]')

			fig.tight_layout()
			fig.savefig(sample)
			plt.show()

		except(FileNotFoundError):
			print('Sample name not found.')

	#----------------------------------------------------------------------
	def IVsweep(self, sample):
		'''K2636 IV sweep'''
		try:
			begin_time = time.time()
			self.loadTSP('iv-sweep.tsp')
			self.runTSP()
			df = self.readBufferIV()
			output_name = str(sample + '-iv-sweep.csv')
			df.to_csv(output_name, sep='\t', index=False)
			finish_time = time.time()
			print('IV sweep complete. Elapsed time %.2f mins.' %((finish_time - begin_time)/60))

		except(AttributeError):
			print('Cannot perform IV sweep: no keithley connected.')

	#----------------------------------------------------------------------
	def Output(self, sample):
		'''K2636 Output sweeps'''
		try:
			begin_time = time.time()
			self.loadTSP('output-charact.tsp')
			self.runTSP()
			df = self.readBuffer()
			output_name = str(sample + '-output.csv')
			df.to_csv(output_name, sep='\t', index=False)
			finish_time = time.time()
			print('Output sweeps complete. Elapsed time %.2f mins.' %((finish_time - begin_time)/60))

		except(AttributeError):
			print('Cannot perform output sweep: no keithley connected.')


	#----------------------------------------------------------------------
	def Transfer(self, sample):
		'''K2636 Transfer sweeps'''
		try:
			begin_time = time.time()
			self.loadTSP('transfer-charact.tsp')
			self.runTSP()
			df = self.readBuffer()
			output_name = str(sample + '-transfer.csv')
			df.to_csv(output_name, sep='\t', index=False)
			finish_time = time.time()
			print('Transfer curves measured. Elapsed time %.2f mins.' %((finish_time - begin_time)/60))

		except(AttributeError):
			print('Cannot perform transfer sweep: no keithley connected.')

########################################################################


if __name__ == '__main__':
	'''For testing methods in the K2636 class'''
	keithley = K2636(address='ASRL/dev/ttyUSB0', read_term='\n', baudrate=57600)
	sample = 'blank-20-1'
	keithley.IVsweep(sample)
	#keithley.Output(sample)
	keithley.Transfer(sample)
	keithley.DisplayMeasurement(sample)
	keithley.closeConnection()
© 2017 GitHub, Inc.
Terms
Privacy
Security
Status
Help
Contact GitHub
API
Training
Shop
Blog
About