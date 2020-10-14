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
from cron_descriptor import get_description, ExpressionDescriptor

# Control uses this
def ReadJSON(json_data_filename="irrigator.json"):
    try:
        json_data_file = open(json_data_filename, 'r')
        json_data_string = json_data_file.read()
        json_data_dict = json.loads(json_data_string)
        json_data_file.close()
    except:
        json_data_dict = createjson()
        WriteJSON(json_data_dict)
    return(json_data_dict)

# Control uses this
def WriteJSON(json_data_dict, json_data_filename="irrigator.json"):
	json_data_string = json.dumps(json_data_dict)
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

def createjson():
    irrigator = {}

    irrigator['controls'] = {
        'manual_override': False, # For stopping any current activity
        'active': False # Control.py process is currently active/running
    }

    irrigator['settings'] = {
        'target_sys': 'None', # Select CHIP, RasPi or test
        'zone_gate': 29 # This is the GPIO pin responsible for gating the sprinkler pins during power-up, shutdown, and reboot
    }

    irrigator['wx_data'] = {
        'apikey': '123456789abcdefghijklmnopqrstuvxyz', # OpenWeatherMap APIkey
        'latlong': '44.0611151,-121.3846839',
        'location' : 'Bend, OR',
        'min_temp': 32,
        'max_temp': 100,
        'percip' : 0.2, # Max Percipitation Cancel Irrigation
        'disable': False  # Disable Weather Restrictions (i.e. Force)
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