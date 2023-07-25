#!/usr/bin/env python3

# *****************************************
# Irrigator Raspberry Pi Interface Library
# *****************************************
#
# Description: This library supports controlling
#  via the Raspberry Pi GPIOs, 
#  to a 8-channel relay
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import RPi.GPIO as GPIO

# *****************************************
# Class Definition
# *****************************************

class Platform:

	def __init__(self, _outpins, relay_trigger=0):
		self.outpins = _outpins # { 'zone_00' : 17, 'zone_01': 18, etc... }
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BOARD)
		for item in self.outpins:
			GPIO.setup(self.outpins[item], GPIO.OUT, initial=(not relay_trigger)) #Set the Zone Pins to 'Off'
	
	def setrelay(self, value, zonename):
		try: 
			GPIO.output(int(self.outpins[zonename]), value)
		except:
			print(f'An exception occurred when changing zone {zonename} to {value}')
			raise
			return(1)
		return(0) # Return ErrorCode = 0
	
	def getoutputstatus(self):
		current = {}
		for item in self.outpins:
			current[item] = GPIO.input(int(self.outpins[item]))
		return(current)
	
	def cleanup(self):
		GPIO.cleanup()
