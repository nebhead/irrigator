#!/usr/bin/env python3

# *****************************************
# irrigator - control script
# *****************************************
#
# Description: This script controls the sprinkler relays and turns
# selected relays on/off
#
# control.py -z[xx] -d[xxx] -f
#	-z[xx]		Zone 		Turn on Zone 1,2,3,4
#	-d[xxx] 	Duration	Runtime in minutes
#	-f			Force		Force Multiple Zones or Ignore Weather
#	-i			Init		Initialize Relays to OFF
#	-w[xxxxx]	Weather		Zip Code
#
# This script runs as a separate process from the Flask / Gunicorn
# implementation which handles the web interface.
#
# *****************************************

import sys
import argparse
import time
import datetime
import os
import json
from common import *

def Irrigate(platform, zonename, duration, json_data_filename):
	# *****************************************
	# Function: Irrigate
	# Input: platform, str zonename, int duration, str json_data_filename
	# Description: Turn on relay for duration
	# *****************************************
	errorcode = 0

	event = f"Turning on Zone: {zonename} for {duration} minutes."
	WriteLog(event)
	errorcode = errorcode + platform.setrelay(0, zonename) # Turning on Zone

	starttime = time.time()
	now = starttime

	while(now - starttime < (duration*60)):
		if(CheckOverride(json_data_filename) > 0):
			break
		else:
			time.sleep(1)  # Pause for 1 Second
		now = time.time()

	event = f"Turning off Zone: {zonename}."
	WriteLog(event)

	errorcode = errorcode + platform.setrelay(1, zonename) # Turning off Zone
	if (CheckOverride(json_data_filename) > 0):
		errorcode = 42

	return(errorcode)

def CheckOverride(json_data_filename):
	json_data_dict = ReadJSON(json_data_filename)

	if (json_data_dict['controls']['manual_override'] == True):
		errorcode = 42
	else:
		errorcode = 0

	return (errorcode)

def checkrain():
	# *****************************************
	# Function: checkrain
	# Input: none
	# Output: amount, errorcode
	# Description:  Read percipitation amount for last day from file
	# *****************************************
	errorcode = 0
	try:
		wx_data_file = open("wx_status.json", "r")
		json_data_string = wx_data_file.read()
		wx_status = json.loads(json_data_string)
		wx_data_file.close()
		amount = wx_status['percipitation']

	except:
		amount = 0.0
		errorcode = 6

	return(amount, errorcode)

# *****************************************
# Main Program Start
# *****************************************

# control.py -z[xx] -d[xxx] -f
#	-z [name]		Zone 		Manual Mode: Turn on Zone [name]
#	-d [xxx] 		Duration	Manual Mode: Runtime in minutes
#	-f				Force		ALL Modes: Ignore Rain
#	-i				Init		ALL Modes: Initialize Relays to OFF on reboot
#   -j [filename]	JSON File  	Alternate JSON File [default: irrigator.json]
#	-s [schedule]   Schedule	Auto Mode: Select Schedule Run [name]

event = "***** Control Script Starting *****"
WriteLog(event)

# Parse Input Arguements
parser = argparse.ArgumentParser(description='Irrigator - Sprinkler Zone Control Script.  Usage as follows: ')
parser.add_argument('-z','--zone', help='Manually turn on zone. (-z [zone_name])',required=False)
parser.add_argument('-d','--duration',help='Duration to turn on zone. (NOTE: Works with manual zone control only)', required=False)
parser.add_argument('-s','--schedule',help='Name of schedule/program to run. Auto-Mode.', required=False)
parser.add_argument('-j','--json',help='Use an alternative JSON settings file.  Default = [irrigator.json]', required=False)
parser.add_argument('-f','--force',help='Force irrigation regardless of weather', action='store_true',required=False)
parser.add_argument('-i','--init',help='Initialize relays (on first boot).',action='store_true',required=False)
args = parser.parse_args()

# *****************************************
# Set variables (json,schedule,zone,duration,location)
# *****************************************
errorcode = 0

if(args.json):
    json_data_filename = args.json
else:
    json_data_filename = "irrigator.json"

# General open & read JSON into a dictionary
json_data_dict = ReadJSON(json_data_filename)

# Flag Control Active at beginning of script
json_data_dict['controls']['active'] = True
WriteJSON(json_data_dict, json_data_filename)

if(args.schedule):
    schedule_selected = args.schedule
    schedule_run = True
else:
    schedule_selected = "null"
    schedule_run = False

if(args.zone):
	zone = args.zone
else:
	zone = "null"

if(args.duration):
	duration = int(args.duration)
else:
	duration = 0

force = args.force
init = args.init

# Check for Rain
api_key = json_data_dict['wx_data']['apikey']
percip, errorcode = checkrain()
event = "Percipitation in last 24 hours: " + str(percip)
WriteLog(event)

if(errorcode == 1):
	event = "Invalid Latitude / Longitude Format."
	WriteLog(event)
elif(errorcode == 6):
	event = "Weather Fetch Failed for some reason.  Bad API?  Network Issue?"
	WriteLog(event)

# If string "rain" found in weather output, then
if (percip > json_data_dict['wx_data']['percip']):
	raining = True
else:
	raining = False

# *****************************************
# Initialize Relays Globally
# *****************************************

# Init outpin structure
outpins = {}
for index_key, index_value in json_data_dict['zonemap'].items():
	outpins[index_key] = json_data_dict['zonemap'][index_key]['GPIO_mapping']
outpins['gate'] = json_data_dict['settings']['zone_gate']

# Init platform object
if(json_data_dict['settings']['target_sys'] == "CHIP"):
	event = "Initializing Relays on CHIP."
	WriteLog(event)
	from platform_chip import Platform 
	platform = Platform(outpins)

elif(json_data_dict['settings']['target_sys'] == "RasPi"):
	event = "Initializing Relays on Raspberry Pi."
	WriteLog(event)
	from platform_raspi import Platform 
	platform = Platform(outpins)

else:
	event = "Initializing Relays on NONE.  Prototype Mode."
	WriteLog(event)
	from platform_prototype import Platform 
	platform = Platform(outpins)

# *****************************************
# Main Program If / Else Tree
# *****************************************

if (init):
	event = "Initialize Relays Selected."
	WriteLog(event)
	errorcode = 0
# Schedule Run
elif ((schedule_run == True) and ((raining == False) or (force == True))):
	event = "Schedule Run Selected with Schedule: " + schedule_selected
	WriteLog(event)

	if (schedule_selected in json_data_dict['schedules']):
		event = schedule_selected + " found in JSON file. Running Now."
		WriteLog(event)
		json_data_dict['schedules'][schedule_selected]['start_time']['active'] = True # Set Schedule active = True
		WriteJSON(json_data_dict, json_data_filename)
		for index_key, index_value in sorted(json_data_dict['schedules'][schedule_selected]['zones'].items()):
			if ((json_data_dict['zonemap'][index_key]['enabled'] == True) and (index_value['duration'] != 0)):  # Check if zone enabled and has greater than 0 time
				json_data_dict['zonemap'][index_key]['active'] = True # Set Zone Active = False
				WriteJSON(json_data_dict, json_data_filename)
				# Run Zone
				errorcode = Irrigate(platform, index_key, index_value['duration'], json_data_filename)
				# Read latest control data from JSON file (just in case anything changed)
				json_data_dict = ReadJSON(json_data_filename)
				json_data_dict['zonemap'][index_key]['active'] = False # Set Zone Active = False
				WriteJSON(json_data_dict, json_data_filename)
		json_data_dict['schedules'][schedule_selected]['start_time']['active'] = False # Set Schedule active = False
		WriteJSON(json_data_dict, json_data_filename)

	else:
		event = f"{schedule_selected} not found in JSON file.  Exiting Now."
		WriteLog(event)
		errorcode = 1
# Manual Run
elif ((schedule_run == False) and ((raining == False) or (force == True))):
	event = "Manual Run Selected."
	WriteLog(event)
	if (zone in json_data_dict['zonemap']):
		json_data_dict['zonemap'][zone]['active'] = True # Set Zone Active = True
		WriteJSON(json_data_dict, json_data_filename)
		# Run Zone
		errorcode = Irrigate(platform, zone, duration, json_data_filename)
		json_data_dict['zonemap'][zone]['active'] = False # Set Zone Active = False
		WriteJSON(json_data_dict, json_data_filename)
	else:
		event = f"{zone} not found in JSON file.  Exiting."
		WriteLog(event)
		errorcode = 1

# Weather Cancellation
elif (raining == True):
	event = "Irrigation cancelled due to percipitation exceeding limits."
	WriteLog(event)
	errorcode = 1

# Catch All Conditions
else:
	event = "No Action."
	WriteLog(event)
	errorcode = 0

# Cleanup GPIOs if on SBC
platform.cleanup()

# Write Result and exit
event = "Exiting with errorcode = " + str(errorcode)
WriteLog(event)
event = "***** Control Script Ended *****"
WriteLog(event)

# Flag Control Active at beginning of script
json_data_dict['controls']['active'] = False
json_data_dict['controls']['manual_override'] = False
WriteJSON(json_data_dict, json_data_filename)

exit()
