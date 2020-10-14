#!/usr/bin/env python3

# *****************************************
# Irrigator Prototype Interface Library
# *****************************************
#
# Description: This library supports controlling
#  via the prototype GPIOs, 
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

# None

# *****************************************
# Class Definition
# *****************************************

class Platform:
    def __init__(self, _outpins):
        self.outpins = _outpins # { 'zone_00' : 17, 'zone_01': 18, etc... }
        self.current = {}
        for item in self.outpins:
            self.current[item] = 1 #Set the Zone Pins High
    
    def setrelay(self, value, zonename):
        try: 
            self.current['zonename'] = value
        except:
            print(f'An exception occurred when changing zone {zonename} to {value}')
            return(1)
        return(0) # Return ErrorCode = 0
	
    def getoutputstatus(self):
        return(self.current)
	
    def cleanup(self):
        print('Cleaning up.')
        return()
