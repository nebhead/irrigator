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

import CHIP_IO.GPIO as GPIO

# *****************************************
# Class Definition
# *****************************************
class Platform:
	def __init__(self, _outpins, relay_trigger=0):
		self.outpins = _outpins # { 'zone_00' : 17, 'zone_01': 18, etc... }
		# Set the Zone / Gate Pins High
		for item in self.outpins:
			pin_name = "XIO-P" + str(self.outpins[item])
			GPIO.setup(pin_name, GPIO.OUT)
			GPIO.output(pin_name, GPIO.HIGH)
			if(relay_trigger == 1):
				GPIO.output(pin_name, GPIO.LOW)
			else:
				GPIO.output(pin_name, GPIO.HIGH)

	def setrelay(self, value, zonename):
		try:
			pin_name = "XIO-P" + str(self.outpins[zonename])
			if(value == 0):
				GPIO.output(pin_name, GPIO.LOW)
			else:
				GPIO.output(pin_name, GPIO.HIGH)
		except:
			print(f'An exception occurred when changing zone {zonename} to {value}')
			return(1)
		return(0) # Return ErrorCode = 0

	def getoutputstatus(self):
		current = {}
		for item in self.outpins:
			current[item] = GPIO.input(self.outpins[item])
		return current

	def cleanup(self):
		GPIO.cleanup()