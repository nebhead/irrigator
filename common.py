#!/usr/bin/env python3

# *****************************************
# irrigator - common functions
# *****************************************
#
# Description: This script contains common functions
#
# *****************************************

import json
import datetime
import io
from cron_descriptor import get_description, ExpressionDescriptor

# Control uses this
def ReadJSON(json_data_filename="irrigator.json", type="settings"):
    try:
        json_data_file = open(json_data_filename, 'r')
        json_data_string = json_data_file.read()
        json_data_dict = json.loads(json_data_string)
        json_data_file.close()
    except(IOError, OSError):
		# File not found, write defaults
        event = f"Exception occurred when reading {json_data_filename}.  File not found.  Creating the file with default settings."
        WriteLog(event)
        if type == 'weather': 
            json_data_dict = create_wx_json()
            WriteJSON(json_data_dict, json_data_filename='wx_status.json')
        else: 
            json_data_dict = create_json()
            WriteJSON(json_data_dict)
    except(ValueError):
		# A ValueError Exception occurs when multiple accesses collide, this code attempts a retry.
        event = f'Exception occurred when reading {json_data_filename}.  Value Error Exception - JSONDecodeError.  Retrying.'
        WriteLog(event)
        json_data_file.close()
		# Retry Reading JSON
        json_data_dict = ReadJSON(json_data_filename, type)

    if type != 'weather':
        # Check relay trigger which was added post-initial release 
        if 'relay_trigger' not in json_data_dict['settings'].keys():
            relay_trigger = 0  # Set default to active low (0) triggered relays 
            json_data_dict['settings']['relay_trigger'] = 0  # set the default to active low (0) triggered in settings, and save
            WriteJSON(json_data_dict)

    return(json_data_dict)

# Control uses this
def WriteJSON(json_data_dict, json_data_filename="irrigator.json"):
	json_data_string = json.dumps(json_data_dict, indent=2)
	with open(json_data_filename, 'w') as settings_file:
	    settings_file.write(json_data_string)

def WriteLog(event):
	# *****************************************
	# Function: WriteLog
	# Input: str event
	# Description: Write event to event.log
	#  Event should be a string.
	# *****************************************
	now = str(datetime.datetime.now())
	now = now[0:19] # Truncate the microseconds

	logfile = open("events.log", "a")
	logfile.write(now + ' ' + event + '\n')
	logfile.close()

def create_json():
    irrigator = {}

    irrigator['controls'] = {
        'manual_override': False, # For stopping any current activity
        'active': False # Control.py process is currently active/running
    }

    irrigator['settings'] = {
        'target_sys': 'None',  # Select CHIP, RasPi or test
        'zone_gate': 29,       # This is the GPIO pin responsible for gating the sprinkler pins during power-up, shutdown, and reboot
        'relay_trigger' : 0    # 0 for active low relays, 1 for active high relays 
    }

    irrigator['wx_data'] = {
        'apikey': '123456789abcdefghijklmnopqrstuvxyz', # OpenWeatherMap APIkey
        'lat': '44.0611151',
        'long': '-121.3846839', 
        'location' : 'Bend, OR',
        'temp_enable' : True,
        'min_temp': 32,
        'max_temp': 100,
        'precip' : 0.2,  # Max Precipitation Cancel Irrigation
        'history_enable': True,  # Disable Weather Restrictions (i.e. Force)
        'history_hours': 24,  # Number of hours of history to track precipitation
        'forecast_hours': 24,  # Number of hours to forecast precipitation
        'forecast_enable': True,  # Enable forecast checking
        'forecast_history_enable': True,  # Enable forecast + history > precip max, cancel irrigation
        'units': 'F'
    }

    irrigator['zonemap'] = {
        'zone_01': {
            'GPIO_mapping': 31,
            'enabled': True,
            'active': False
        },
        'zone_02': {
            'GPIO_mapping': 32,
            'enabled': True,
            'active': False
        },
        'zone_03': {
            'GPIO_mapping': 33,
            'enabled': True,
            'active': False
        },
        'zone_04': {
            'GPIO_mapping': 35,
            'enabled': False,
            'active': False
        },
        'zone_05': {
            'GPIO_mapping': 36,
            'enabled': False,
            'active': False
        },
        'zone_06': {
            'GPIO_mapping': 37,
            'enabled': False,
            'active': False
        },
        'zone_07': {
            'GPIO_mapping': 38,
            'enabled': False,
            'active': False
        },
    }
    # CRON Format
    # +---------- minute (0 - 59)
    # | +-------- hour (0 - 23)
    # | | +------ day of month (1 - 31)
    # | | | +---- month (1 - 12)
    # | | | | +-- day of week (0 - 6 => Sunday - Saturday, or
    # | | | | |                1 - 7 => Monday - Sunday)
    # * * * * * command to be executed

    # Daily
    # m h * * * command

    # Even Days
    # m h 2-30/2 * * command

    # Odd Days
    # m h 1-31/2 * * command

    # Custom Days
    # m h * * SUN,MON,TUE,WED,THU,FRI,SAT command

    irrigator['schedules'] = {
        'FrontYard': {
            'start_time': {
                'enabled': False,
                'minute': 30,
                'hour': 6,
                'day_of_month': '*',
                'month': '*',
                'day_of_week': '*',
                'cron_string': 'null',
                'human_readable': 'null',
                'active': False
            },
            'zones': {
                'zone_01': {
                    'duration': 10
                },
                'zone_02': {
                    'duration': 10
                }
            }
        },
        'BackYard': {
            'start_time': {
                'enabled': False,
                'minute': 0,
                'hour': 18,
                'day_of_month': '*',
                'month': '*',
                'day_of_week': 'SUN,MON,TUE,WED,THU,FRI,SAT',
                'cron_string': 'null',
                'human_readable': 'null',
                'active': False
            },
            'zones': {
                'zone_01': {
                    'duration': 1
                },
                'zone_02': {
                    'duration': 1
                },
                'zone_03': {
                    'duration': 1
                }
            }
        }
    }

    for index_a, index_b in irrigator['schedules'].items():
        temp_cron_str = str(index_b['start_time']['minute']) + " " + str(index_b['start_time']['hour']) + " " + index_b['start_time']['day_of_month'] + " " + index_b['start_time']['month'] + " " + index_b['start_time']['day_of_week']
        index_b['start_time']['cron_string'] = temp_cron_str
        index_b['start_time']['human_readable'] = get_description(temp_cron_str)

    return(irrigator)

def create_wx_json():
    wx_status = {}
    wx_status = {
		'summary' : 'Nothing to Report',
		'icon' : '/static/img/wx-icons/unknown.png',
		'updated' : '', 
		'last_rain_update' : 0,
		'rain_history_list' : [],
        'rain_history_total' : 0,
        'rain_current' : 0,
		'rain_forecast' : 0.0,
        'temp_current' : 0,
	}
    return(wx_status)


# **************************************
# is_raspberrypi() function borrowed from user https://raspberrypi.stackexchange.com/users/126953/chris
# in post: https://raspberrypi.stackexchange.com/questions/5100/detect-that-a-python-program-is-running-on-the-pi
# **************************************
def is_raspberry_pi():
	"""
	Check if device is a Raspberry Pi

	:return: True if Raspberry Pi. False otherwise
	"""
	try:
		with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
			if 'raspberry pi' in m.read().lower(): return True
	except Exception:
		pass
	return False