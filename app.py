#!/usr/bin/env python3

# *****************************************
# irrigator - app script
# *****************************************
#
# Description: This script defines the WebUI
#
# *****************************************

from flask import Flask, request, render_template, make_response
import time
import datetime
import os
import json
from cron_descriptor import get_description, ExpressionDescriptor
from crontab import CronTab
from common import *

# Modify this path for your installation
pathtoirrigator = "/usr/local/bin/irrigator"

app = Flask(__name__)

@app.route('/<action>', methods=['POST','GET'])
@app.route('/', methods=['POST','GET'])
def dashboard(action=None):
	json_data_dict = ReadJSON()
	wx_status = ReadJSON('wx_status.json', type="weather")

	if (request.method == 'POST') and (action == 'manualcontrol'):
		response = request.form
		print(response) #DEBUG

		if('stop' in response):
			# Stop Schedule OR Zone
			print('Stopping Schedule or Zone.') #DEBUG
			json_data_dict['controls']['manual_override'] = True
			WriteJSON(json_data_dict)
			# loop until override is cleared
			override_delay = True
			while(override_delay):
				json_data_dict = ReadJSON()
				override_delay = json_data_dict['controls']['manual_override']
				time.sleep(0.5)

		elif('startsched' in response):
			# Start Schedule
			print('Starting Schdedule') #DEBUG

			if(json_data_dict['controls']['active'] == False):
				if(json_data_dict['settings']['target_sys'] == 'None'):
					execute_string = "python3 control.py -f -s " + str(response['startsched'] + " &") # For running on None
				else:
					execute_string = "sudo python3 control.py -f -s " + str(response['startsched'] + " &")  # For running on CHIP or RasPi
				os.system(execute_string)
				start_delay = False
				while(start_delay == False):
					json_data_dict = ReadJSON()
					start_delay = json_data_dict['controls']['active']
					time.sleep(1)
				json_data_dict = ReadJSON()
		
		elif('startzone' in response):
			# Start Zone
			print('Starting Zone') #DEBUG

			index = 'duration_' + response['startzone']
			print(index) #DEBUG
			duration = '10'
			if(index in response):
				if(response[index] != ''):
					duration = str(response[index])
			print(duration) #DEBUG
			if(json_data_dict['controls']['active'] == False):
				if(json_data_dict['settings']['target_sys'] == 'None'):
					execute_string = "python3 control.py -f -z " + str(response['startzone'] + " -d " + duration + " &") # For running on None
				else:
					execute_string = "sudo python3 control.py -f -z " + str(response['startzone'] + " -d " + duration + " &") # For running on None
				os.system(execute_string)
				start_delay = False
				while(start_delay == False):
					json_data_dict = ReadJSON()
					start_delay = json_data_dict['controls']['active']
					time.sleep(1)
				json_data_dict = ReadJSON()

	return render_template('index.html', jdict=json_data_dict, wx_status=wx_status)

@app.route('/activesched', methods=['POST','GET'])
def activesched(action=None):
	# Return HTML for active schedules
	json_data_dict = ReadJSON()
	htmlout = '<div class=\"alert alert-info\" role=\"alert\"><span class=\"glyphicon glyphicon-info-sign\"></span><strong> No schedules currently active.</div>'
	for index_key, index_value in json_data_dict['schedules'].items():
		if json_data_dict['schedules'][index_key]['start_time']['active'] == True:
			htmlout = f'<div class=\"alert alert-warning\" role=\"alert\"><span class=\"glyphicon glyphicon-info-sign\"></span><strong> Schedule: </strong> {index_key} is active.</div>'
			break
	return(htmlout)

@app.route('/activezone', methods=['POST','GET'])
def activezone(action=None):
	# Return HTML for active zone
	json_data_dict = ReadJSON()
	htmlout = '<div class=\"alert alert-info\" role=\"alert\"><span class=\"glyphicon glyphicon-info-sign\"></span><strong> No zones currently active. </strong></div>'
	for index_key, index_value in json_data_dict['zonemap'].items():
		if json_data_dict['zonemap'][index_key]['active'] == True:
			htmlout = f'<div class=\"alert alert-warning\" role=\"alert\"><span class=\"glyphicon glyphicon-info-sign\"></span><strong> Zone: </strong> {index_key} is active.</div>'
			break
	return(htmlout)

@app.route('/manual', methods=['GET'])
def manual(action=None):
	# Return HTML for schedule buttons
	json_data_dict = ReadJSON()
	return render_template('manual.html', jdict=json_data_dict) 

@app.route('/shortlog', methods=['GET'])
def shortlog(action=None):
	# Return HTML for event list
	event_list, num_events = readeventlog()
	return render_template('shortlog.html', event_list=event_list, num_events=num_events) 

@app.route('/schedule/<action>', methods=['POST','GET'])
@app.route('/schedule', methods=['POST','GET'])
def schedule(action=None):
	json_data_dict = ReadJSON()
	success = True
	detail = ""

	if (request.method == 'POST') and (action == 'modify'):
		# Get POST data in multidict 'response'
		response = request.form
		if('sched_name' in response):
			if(response['sched_name'] in json_data_dict.get('schedules', {})):

				if('delete' in response):
					# Remove schedule from crontab if enabled
					update_crontab(json_data_dict, response['sched_name'], 'delete')
					del json_data_dict['schedules'][response['sched_name']]
				else:
					#frequency (daily, even, odd, custom (SUN, MON, TUE, WED, THU, FRI, SAT))
					if('daily' in response['frequency']):
						print('Daily Selected.')
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '*'
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_week'] = '*' # Default to daily


					if('even' in response['frequency']):
						print('Even Selected.')
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '2-30/2'
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_week'] = '*' # Default to daily


					if('odd' in response['frequency']):
						print('Odd Selected.')
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '1-31/2'
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_week'] = '*' # Default to daily


					if('custom' in response['frequency']):
						print('Custom Selected.')
						custom_days_str = ""
						if('sunday' in response):
							custom_days_str = custom_days_str + ",Sun"
						if('monday' in response):
							custom_days_str = custom_days_str + ",Mon"
						if('tuesday' in response):
							custom_days_str = custom_days_str + ",Tue"
						if('wednesday' in response):
							custom_days_str = custom_days_str + ",Wed"
						if('thursday' in response):
							custom_days_str = custom_days_str + ",Thu"
						if('friday' in response):
							custom_days_str = custom_days_str + ",Fri"
						if('saturday' in response):
							custom_days_str = custom_days_str + ",Sat"
						if(custom_days_str == ""):
							json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '*'
							json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_week'] = '*' # Default to daily
							print('Custom values not selected. Defaulting to daily frequency.')
						else:
							json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '*'
							json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_week'] = custom_days_str[1:] # Default to daily
							print(custom_days_str[1:])

					#hour (int) (test if 0-23)
					if('hour' in response):
						if(response['hour'] != ''):
							if(int(response['hour'])>=0) and (int(response['hour'])<=23):
								json_data_dict['schedules'][response['sched_name']]['start_time']['hour'] = int(response['hour'])
							else:
								success = False
								detail = detail + "\nHour is not valid. (Must be a number from 0-23.) "

					#min (int) (test if 0-59)
					if('minute' in response):
						if(response['minute'] != ''):
							if(int(response['minute'])>=0) and (int(response['minute'])<60):
								json_data_dict['schedules'][response['sched_name']]['start_time']['minute'] = int(response['minute'])
							else:
								success = False
								detail = detail + "\nMinute is not valid. (Must be a number from 0-59.) "

					#duration_zonename (int) (test if 0-120)
					for dur_key in response:
						if dur_key.startswith('duration_'):
							tmp_zone_name = dur_key[9:] # Isolate the zone name from the key value (i.e. remove 'duration_')
							if(tmp_zone_name in json_data_dict['schedules'][response['sched_name']].get('zones', {})):
								print("Matched Zone in schedule: " + response['sched_name'])
								if(response[dur_key] != ''):
									json_data_dict['schedules'][response['sched_name']]['zones'][tmp_zone_name]['duration'] = int(response[dur_key])
							elif(response[dur_key] != ''):
								json_data_dict['schedules'][response['sched_name']]['zones'][tmp_zone_name]={'duration': int(response[dur_key])}

					# Fill in CRON Strings
					temp_cron_str = build_CRON_string(json_data_dict['schedules'][response['sched_name']])
					json_data_dict['schedules'][response['sched_name']]['start_time']['cron_string'] = temp_cron_str
					json_data_dict['schedules'][response['sched_name']]['start_time']['human_readable'] = get_description(temp_cron_str)

					# Check if the schedule is enabled, set enabled to True, Write CRON string
					if('enabled' in response):
						if(response['enabled']=='on'):
							json_data_dict['schedules'][response['sched_name']]['start_time']['enabled'] = True
							# Update the system crontab
							update_crontab(json_data_dict, response['sched_name'], 'update')
					else:
						json_data_dict['schedules'][response['sched_name']]['start_time']['enabled'] = False
						# Update the system crontab
						update_crontab(json_data_dict, response['sched_name'], 'disable')

			else:
				success = False
				detail = "Schedule Name: " + str(response['sched_name']) + " not found in data file."

			#Write Schedule to json_data_dict if success = True
			if(success==True):
				print('Writing JSON data to file.')
				WriteJSON(json_data_dict) 

				conflict_found, conflict_msg = CheckConflicts(json_data_dict)

				if(conflict_found):
					success = False
					detail = conflict_msg

		else:
			success = False
			detail = "sched_name not returned. No Action taken."


	# ********* Add Schedule
	elif (request.method == 'POST') and (action == 'add'):
		# Get POST data in multidict 'response'
		response = request.form
		# Check if Schedule Name exists in json_data_dict
		# If not, build schedule and add to json_data_dict
		# Example:
		if('sched_name' in response):
			#Check for special characters
			special_chars = CheckString(str(response['sched_name']))

			if(special_chars != ""):
				success = False
				detail = "Special Characters or Space Character Found: \"" + special_chars + "\" in " + response['sched_name'] + ".  Remove and try again."

			elif(response['sched_name'] == '') or (response['sched_name'] in json_data_dict.get('schedules', {})):
				success = False
				detail = "Either schedule name is blank or schedule name exists in the data file.  Choose a unique name."
			else:
				# Initialize New Dict
				json_data_dict['schedules'][response['sched_name']] = {
				    'start_time': {
				        'enabled': True,
				        'minute': 0,
				        'hour': 0,
				        'day_of_month': '*',
				        'month': '*',
				        'day_of_week': '*',
						'cron_string': 'null',
						'human_readable': 'null',
						'active': False
				    },
					'zones': {}
				}
				#frequency (daily, even, odd, custom (SUN, MON, TUE, WED, THU, FRI, SAT))
				if('daily' in response['frequency']):
					json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '*'

				if('even' in response['frequency']):
					json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '2-30/2'

				if('odd' in response['frequency']):
					json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '1-31/2'

				if('custom' in response['frequency']):
					custom_days_str = ""
					if('sunday' in response):
						custom_days_str = custom_days_str + ",Sun"
					if('monday' in response):
						custom_days_str = custom_days_str + ",Mon"
					if('tuesday' in response):
						custom_days_str = custom_days_str + ",Tue"
					if('wednesday' in response):
						custom_days_str = custom_days_str + ",Wed"
					if('thursday' in response):
						custom_days_str = custom_days_str + ",Thu"
					if('friday' in response):
						custom_days_str = custom_days_str + ",Fri"
					if('saturday' in response):
						custom_days_str = custom_days_str + ",Sat"
					if(custom_days_str == ""):
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '*'
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_week'] = '*' # Default to daily
					else:
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_month'] = '*'
						json_data_dict['schedules'][response['sched_name']]['start_time']['day_of_week'] = custom_days_str[1:] # Default to daily

				#hour (int) (test if 0-23)
				if('hour' in response):
					if(response['hour'] != ''):
						if(int(response['hour'])>=0) and (int(response['hour'])<=23):
							json_data_dict['schedules'][response['sched_name']]['start_time']['hour'] = int(response['hour'])
						else:
							success = False
							detail = detail + "\nHour is not valid. (Must be a number from 0-23.) "

				#min (int) (test if 0-59)
				if('minute' in response):
					if(response['minute'] != ''):
						if(int(response['minute'])>=0) and (int(response['minute'])<60):
							json_data_dict['schedules'][response['sched_name']]['start_time']['minute'] = int(response['minute'])
						else:
							success = False
							detail = detail + "\nMinute is not valid. (Must be a number from 0-59.) "

				#duration_zonename (int) (test if 0-120)
				for dur_key in response:
					if dur_key.startswith('duration_'):
						tmp_zone_name = dur_key[9:] # Isolate the zone name from the key value (i.e. remove 'duration_')

						#if('zones' in json_data_dict['schedules'].get([response['sched_name']], {})):
						if(response[dur_key] == ''):
							json_data_dict['schedules'][response['sched_name']]['zones'][tmp_zone_name]={'duration': 0}
						else:
							json_data_dict['schedules'][response['sched_name']]['zones'][tmp_zone_name]={'duration': int(response[dur_key])}

				# Fill in CRON Strings
					temp_cron_str = build_CRON_string(json_data_dict['schedules'][response['sched_name']])
					json_data_dict['schedules'][response['sched_name']]['start_time']['cron_string'] = temp_cron_str
					json_data_dict['schedules'][response['sched_name']]['start_time']['human_readable'] = get_description(temp_cron_str)

				# Check if the schedule is enabled, set enabled to True, Write CRON string
				if('enabled' in response):
					if(response['enabled']=='on'):
						json_data_dict['schedules'][response['sched_name']]['start_time']['enabled'] = True
						# Update the system crontab
						update_crontab(json_data_dict, response['sched_name'], 'add')
				else:
					json_data_dict['schedules'][response['sched_name']]['start_time']['enabled'] = False
					# Update the system crontab
					update_crontab(json_data_dict, response['sched_name'], 'add')
					update_crontab(json_data_dict, response['sched_name'], 'disable')

				#Write Schedule to json_data_dict if success = True
				if(success==True):
					print('Writing JSON data to file.')
					WriteJSON(json_data_dict)
					conflict_found, conflict_msg = CheckConflicts(json_data_dict)
					if(conflict_found):
						success = False
						detail = conflict_msg

	return render_template('schedule.html', jdict=json_data_dict, action=action, success=success, detail=detail)


@app.route('/settings/<action>', methods=['POST','GET'])
@app.route('/settings', methods=['POST','GET'])
def settings(action=None):
	json_data_dict = ReadJSON()
	success = True
	detail = ''

	if (request.method == 'POST') and (action == 'modifyzone'):
		success = True
		detail = ""
		response = request.form

		if('zone_name' in response):
			if(str(response['zone_name']) in json_data_dict.get('zonemap', {})):
				if ('delete' in response):
					del json_data_dict['zonemap'][str(response['zone_name'])]

				else:
					if ('gpio_pin' in response):
						#write to GPIO pin if not empty
						if(response['gpio_pin']!=''):
							json_data_dict['zonemap'][str(response['zone_name'])]['GPIO_mapping'] = int(response['gpio_pin'])

					if ('enabled' in response):
						#write to enabled if not empty
						if(response['enabled']=='on'):
							json_data_dict['zonemap'][str(response['zone_name'])]['enabled'] = True
						else:
							json_data_dict['zonemap'][str(response['zone_name'])]['enabled'] = False

					if ('new_name' in response):
						if (response['new_name'] != ''):
							# Check if name already taken.
							if(str(response['new_name']) == str(response['zone_name'])):
								# New Name is the same as old name, so do nothing
								success = True
							elif(str(response['new_name']) in json_data_dict.get('zonemap', {})):
								success = False
								detail = detail + "Looks like you tried to change the zone name to a name that already exists. \n"
							else:
								#check if any special characters or spaces in name
								special_chars = CheckString(str(response['new_name']))
								if (special_chars == ""):
									#create new dictionary entry and copy contents of old entry to new entry
									json_data_dict['zonemap'][str(response['new_name'])] = json_data_dict['zonemap'][str(response['zone_name'])]
									del json_data_dict['zonemap'][str(response['zone_name'])]
									
									#check schedules to see if the zone that was just changed is used and replace
									for schedule in json_data_dict['schedules']:
										for zone in json_data_dict['schedules'][schedule]['zones']:
											if zone == response['zone_name']:
												json_data_dict['schedules'][schedule]['zones'][str(response['new_name'])] = json_data_dict['schedules'][schedule]['zones'][zone]
												del json_data_dict['schedules'][schedule]['zones'][zone]
												break
								else:
									success = False
									detail = detail + "Special Characters or Space Character Found: \"" + special_chars + "\" in " + str(response['new_name']) + ".  Remove and try again.\n"

			else:
				success = False
				detail = detail + "Yo dawg, we couldn't find the zone you wanted to modify.\n"


		if(success==True):
			print('Success:  Writing JSON data to file.')
			WriteJSON(json_data_dict)  # There be dragons - enable only when tested.


	elif (request.method == 'POST') and (action == 'add'):
		success = True
		detail = ""
		response = request.form

		if ('zone_name' in response):
			if (response['zone_name'] != ''):
				# Check if name already taken.
				if(str(response['zone_name']) in json_data_dict.get('zonemap', {})):
					success = False
					detail = detail + "Looks like you tried add a zone name that already exists. \n"
				else:
					#check if any special characters or spaces in name
					special_chars = CheckString(str(response['zone_name']))
					if (special_chars == ""):
						#create new dictionary entry
						json_data_dict['zonemap'][str(response['zone_name'])] = {
					        'GPIO_mapping': 0,
					        'enabled': False,
					        'active': False
					    }
						if ('gpio_pin' in response):
							#write to GPIO pin if not empty
							if(response['gpio_pin']!=''):
								json_data_dict['zonemap'][str(response['zone_name'])]['GPIO_mapping'] = int(response['gpio_pin'])

						if ('enabled' in response):
							#write to enabled if not empty
							if(response['enabled']=='on'):
								json_data_dict['zonemap'][str(response['zone_name'])]['enabled'] = True
							else:
								json_data_dict['zonemap'][str(response['zone_name'])]['enabled'] = False

					else:
						success = False
						detail = detail + "Special Characters or Space Character Found: \"" + special_chars + "\" in " + str(response['zone_name']) + ".  Remove and try again.\n"
			else:
				success = False
				detail = "No zone name entered."

		if(success==True):
			print('Success:  Writing JSON data to file.')
			WriteJSON(json_data_dict)  # There be dragons - enable only when tested.

	elif (request.method == 'POST') and (action == 'system'):
		success = True
		detail = ""
		response = request.form

		if ('target_sys' in response):
			if(response['target_sys']=='CHIP'):
				json_data_dict['settings']['target_sys'] = 'CHIP'
			elif(response['target_sys']=='RasPi'):
				json_data_dict['settings']['target_sys'] = 'RasPi'
			elif(response['target_sys']=='None'):
				json_data_dict['settings']['target_sys'] = 'None'
			else:
				success = False
				detail = "Unrecognized System Type Selected.\n"
		if ('relay_trigger' in response):
			if(response['relay_trigger'] == '0'):
				json_data_dict['settings']['relay_trigger'] = 0
			elif(response['relay_trigger'] == '1'):
				json_data_dict['settings']['relay_trigger'] = 1
			else:
				success = False
				detail = "Unrecognized Relay Trigger Setting.\n"
		
		if(success==True):
			print('Success:  Writing JSON data to file.')
			WriteJSON(json_data_dict)  


	elif (request.method == 'POST') and (action == 'weather'):
		success = True
		detail = ""
		response = request.form
		update_weather_data = False
		print(response)
		if ('wx_api_key' in response):
			if (response['wx_api_key'] != ''):
				if json_data_dict['wx_data']['apikey'] != str(response['wx_api_key']):
					json_data_dict['wx_data']['apikey'] = str(response['wx_api_key'])
					update_weather_data = True

		if ('home_location' in response):
			if (response['home_location'] != ''):
				if json_data_dict['wx_data']['location'] != str(response['home_location']):
					json_data_dict['wx_data']['location'] = str(response['home_location'])
					update_weather_data = True

		if ('max_precip' in response):
			if (response['max_precip'] != ''):
				if (float(response['max_precip']) > 0) and (float(response['max_precip']) < 10):
					json_data_dict['wx_data']['precip'] = float(response['max_precip'])
				else:
					success = False
					detail = "Max precipitation Out of Bounds.\n"

		if ('history_enable' in response):
			if (response['history_enable'] == 'on'):
				json_data_dict['wx_data']['history_enable'] = True
		else:
			json_data_dict['wx_data']['history_enable'] = False

		if ('history_hours' in response):
			if (response['history_hours'] != ''):
				json_data_dict['wx_data']['history_hours'] = int(response['history_hours'])

		if ('forecast_hours' in response):
			if (response['forecast_hours'] != ''):
				json_data_dict['wx_data']['forecast_hours'] = int(response['forecast_hours'])

		if ('forecast_enable' in response):
			if (response['forecast_enable'] == 'on'):
				json_data_dict['wx_data']['forecast_enable'] = True
		else:
			json_data_dict['wx_data']['forecast_enable'] = False

		if ('forecast_history_enable' in response):
			if (response['forecast_history_enable'] == 'on'):
				json_data_dict['wx_data']['forecast_history_enable'] = True
		else:
			json_data_dict['wx_data']['forecast_history_enable'] = False

		if ('temp_enable' in response):
			if (response['temp_enable'] == 'on'):
				json_data_dict['wx_data']['temp_enable'] = True
		else:
			json_data_dict['wx_data']['temp_enable'] = False

		if ('max_temp' in response):
			if (response['max_temp'] != ''):
				json_data_dict['wx_data']['max_temp'] = int(response['max_temp'])

		if ('min_temp' in response):
			if (response['min_temp'] != ''):
				json_data_dict['wx_data']['min_temp'] = int(response['min_temp'])

		if ('unitsradio' in response):
			if response['unitsradio'] == 'F':
				json_data_dict['wx_data']['units'] = 'F'
			else:
				json_data_dict['wx_data']['units'] = 'C'

		if(success==True):
			WriteJSON(json_data_dict)
			if(update_weather_data):
				execute_string = "python3 openwx.py" # Get weather after updating API Key or Location
				os.system(execute_string) # Execute

	elif (request.method == 'POST') and (action == 'modifygate'):
		success = True
		detail = ""
		response = request.form

		if('zone_gate' in response):
			print('zone_gate selected')
			if(response['zone_gate'] != ''):
				json_data_dict['settings']['zone_gate'] = int(response['zone_gate'])
				WriteJSON(json_data_dict)
			else:
				success = False
				detail = "Invalid GPIO Pin."

		if(success==True):
			print('Success:  Writing JSON data to file.')
			WriteJSON(json_data_dict) 

	return render_template('settings.html', jdict=json_data_dict, action=action, success=success, detail=detail)

@app.route('/admin/<action>')
@app.route('/admin')
def admin(action=None):

	if action == 'factory-reset':
		event = "Admin: Factory Reset"
		WriteLog(event)
		
		json_data_dict = ReadJSON()
		# Kill and running jobs
		if(json_data_dict['settings']['target_sys'] == 'None'):
			execute_string = "python3 control.py -i &"  # For running on None
		else:
			execute_string = "sudo python3 control.py -i &"  # For running on CHIP or RasPi
		os.system(execute_string) # Initialize Relays
		# Remove all Schedules from CronTab
		for schedule_name, schedule_data in json_data_dict['schedules'].items():
			update_crontab(json_data_dict, schedule_name, 'delete')
		# Build new JSON with default values
		json_data_dict = create_json()
		WriteJSON(json_data_dict)
		json_data_dict = create_wx_json()
		WriteJSON(json_data_dict, 'wx_status.json')
		os.system("sudo python3 initcron.py") # Initialize Relays

	elif action == 'controls-reset':
		event = "Admin: Control Reset"
		WriteLog(event)
		json_data_dict = ReadJSON()
		json_data_dict['controls']['manual_override'] = False
		json_data_dict['controls']['active'] = False
		for item in json_data_dict['zonemap']:
			json_data_dict['zonemap'][item]['active'] = False
		for item in json_data_dict['schedules']:
			json_data_dict['schedules'][item]['start_time']['active'] = False
		if(json_data_dict['settings']['target_sys'] == 'None'):
			execute_string = "python3 control.py -i &"  # For running on None
		else:
			execute_string = "sudo python3 control.py -i &"  # For running on CHIP or RasPi
		os.system(execute_string) # Initialize Relays

		WriteJSON(json_data_dict)

	elif action == 'reboot':
		event = "Admin: Reboot"
		WriteLog(event)
		os.system("sleep 3 && sudo reboot &")
		return render_template('shutdown.html', action=action)

	elif action == 'shutdown':
		event = "Admin: Shutdown"
		WriteLog(event)
		os.system("sleep 3 && sudo shutdown -h now &")
		return render_template('shutdown.html', action=action)

	uptime = os.popen('uptime').readline()

	cpuinfo = os.popen('cat /proc/cpuinfo').readlines()

	return render_template('admin.html', action=action, uptime=uptime, cpuinfo=cpuinfo)

@app.route('/eventlog')
def eventlog():
	event_list, num_events = readeventlog()
	return render_template('eventlog.html', event_list=event_list, num_events=num_events)

@app.route('/manifest')
def manifest():
    res = make_response(render_template('manifest.json'), 200)
    res.headers["Content-Type"] = "text/cache-manifest"
    return res

#def checkcputemp():
#	temp = os.popen('vcgencmd measure_temp').readline()
#	return temp.replace("temp=","")

def readeventlog():
	# Read all lines of events.log into an list(array)
	try:
		with open('events.log') as event_file:
			event_lines = event_file.readlines()
			event_file.close()
	# If file not found error, then create events.log file
	except(IOError, OSError):
		event_file = open('events.log', "w")
		event_file.close()
		event_lines = []

	# Initialize event_list list
	event_list = []

	# Get number of events
	num_events = len(event_lines)

	for x in range(num_events):
		event_list.append(event_lines[x].split(" ",2))

	# Error handling if number of events is less than 20, fill array with empty
	if (num_events < 20):
		for line in range((20-num_events)):
			event_list.append(["--------","--:--:--.------","---"])
		num_events = 20

	return(event_list, num_events)

def CheckString(string):
	symbol = "~`!@#$%^&*()+={}[]:>;',</?*+ "
	special_chars = ""

	for index in string:
		if index in symbol:
			special_chars = special_chars + str(index)

	return(special_chars)

def build_CRON_string(sched_dict):
	temp_cron_str = str(sched_dict['start_time']['minute']) + " " + str(sched_dict['start_time']['hour']) + " " + str(sched_dict['start_time']['day_of_month']) + " " + str(sched_dict['start_time']['month']) + " " + str(sched_dict['start_time']['day_of_week'])

	return(temp_cron_str)

def update_crontab(json_data_dict, sched_name, action):
	errorcode = 0
	system_cron = CronTab(user='root')
	entry = 0

	if(action == 'add'):
		command_string = "cd " + pathtoirrigator + " && sudo python3 control.py -s " + sched_name + " &"
		entry = system_cron.new(command=command_string,comment=sched_name)
		entry.setall(json_data_dict['schedules'][sched_name]['start_time']['cron_string'])
		entry.enable()
		system_cron.write()
	else:
		for entry in system_cron.find_comment(sched_name):
			print(entry) # Black Magic for finding the CRON Job
		if (entry==0):
			print("Did not find entry.")
			# If not found, create it.
			command_string = "cd " + pathtoirrigator + " && sudo python3 control.py -s " + sched_name + " &"
			entry = system_cron.new(command=command_string,comment=sched_name)
			entry.setall(json_data_dict['schedules'][sched_name]['start_time']['cron_string'])
			entry.enable()
			system_cron.write()

		if(action == 'delete'):
			system_cron.remove(entry)
			system_cron.write()
		elif(action == 'disable'):
			entry.enable(False)
			system_cron.write()
		elif(action == 'update'):
			entry.setall(json_data_dict['schedules'][sched_name]['start_time']['cron_string'])
			entry.enable()
			system_cron.write()
		else:
			errorcode = 30

	return(errorcode)

def CheckConflicts(json_data_dict):
	# Function to check for Schedule Conflicts
	# Input: JSON Settings
	# Output: Boolean Error, String Conflicted Schedules
	conflict_found = False
	conflict_msg = ""

	print("DEBUG: Checking conflicts.")

	# Loop through schedules
	for schedule_name, schedule_data in json_data_dict['schedules'].items():

	# Store start time in start_time variable
	#   start_time = hour * 60 + minute
	#   end_time = start_time
		print("\nDEBUG: Starting with Schedule Name: " + str(schedule_name))

		start_time = (json_data_dict['schedules'][schedule_name]['start_time']['hour'] * 60) + json_data_dict['schedules'][schedule_name]['start_time']['minute']
		end_time = start_time

		print("DEBUG: start_time: " + str(start_time))

		# Store end time (Loop through zones)
		#   end_time += zone duration
		for zone_name, zone_data in schedule_data['zones'].items():
			print("DEBUG: zone_name: " + str(zone_name) + " duration: " + str(zone_data['duration']))
			end_time += zone_data['duration']

		# Check if the schedule spans to the next day
		if end_time > 1380:
			overnight = True
		else:
			overnight = False

		print("DEBUG: end_time: " + str(end_time))
		print("DEBUG: overnight: " + str(overnight))

		# Check type Even / Odd / Daily or Custom

		if schedule_data['start_time']['day_of_week'] == "*":
			if schedule_data['start_time']['day_of_month'] == "2-30/2":
				day_type = "even"
			elif schedule_data['start_time']['day_of_month'] == "1-31/2":
				day_type = "odd"
			else:
				day_type = "daily"
		else:
			day_type = "custom"

		print("DEBUG: day_type: " + str(day_type))

		# Loop through schedules and look for conflicts
		for compare_name, compare_data in json_data_dict['schedules'].items():

			if((compare_name != schedule_name)and(compare_data['start_time']['enabled'] != False)and(schedule_data['start_time']['enabled'] != False)):
				print("\nDEBUG: Compare to: " + str(compare_name))

				compare_start_time = (json_data_dict['schedules'][compare_name]['start_time']['hour'] * 60) + json_data_dict['schedules'][compare_name]['start_time']['minute']
				print("DEBUG: compare_start_time: " + str(compare_start_time))

				if compare_data['start_time']['day_of_week'] == "*":
					if compare_data['start_time']['day_of_month'] == "2-30/2":
						compare_day_type = "even"
					elif compare_data['start_time']['day_of_month'] == "1-31/2":
						compare_day_type = "odd"
					else:
						compare_day_type = "daily"
				else:
					compare_day_type = "custom"

				print("DEBUG: compare_day_type: " + str(compare_day_type))

				# Comparing Types

				#	Type format... [compare day] to [schedule day]

				#	TYPE 1: Daily to Daily
				#			Odd to odd
				#			Even to Even
				#			Daily to odd
				#			Daily to Even
				#			Odd to daily
				#			Even to daily
				#	TYPE 2: Even to odd
				#			Odd to even
				#	TYPE 3: Custom to custom

				# TYPE1: Check for conflicts with daily, odd or even schedules
				if( (compare_day_type == day_type)or(compare_day_type == "daily")or(day_type == "daily") )and(day_type != "custom"):
					print("DEBUG: TYPE1 Detected.  Checking conflicts with daily, odd or even schedules.")
					if(compare_start_time >= start_time)and(compare_start_time <= end_time):
						print("Conflict Detected.")
						conflict_found = True
						conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
					elif(overnight == True)and(compare_start_time <= end_time - 1380):
						print("Conflict Detected; Next day.")
						conflict_found = True
						conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

				# TYPE2: Check for conflicts where schedules are odd / even but overnight is flagged
				elif( (compare_day_type == "even")and(day_type == "odd") )or( (compare_day_type == "odd")and(day_type == "even") ):
					print("DEBUG: TYPE2 Detected.  Checking conflicts where schedules are odd / even but overnight is flagged.")
					if(overnight == True)and(compare_start_time <= end_time - 1380):
						print("Conflict Detected; Next day.")
						conflict_found = True
						conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

				# TYPE3: Check for conflicts with custom schedules
				elif(compare_day_type == "custom")or(day_type == "custom"):
					print("DEBUG: TYPE3 Detected.  Checking conflicts between custom schedules.")
					if("Mon" in compare_data['start_time']['day_of_week'])and("Mon" in schedule_data['start_time']['day_of_week']):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380)and("Tue" in compare_data['start_time']['day_of_week']):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

					if("Tue" in compare_data['start_time']['day_of_week'])and("Tue" in schedule_data['start_time']['day_of_week']):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380)and("Wed" in compare_data['start_time']['day_of_week']):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

					if("Wed" in compare_data['start_time']['day_of_week'])and("Wed" in schedule_data['start_time']['day_of_week']):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380)and("Thu" in compare_data['start_time']['day_of_week']):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

					if("Thu" in compare_data['start_time']['day_of_week'])and("Thu" in schedule_data['start_time']['day_of_week']):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380)and("Fri" in compare_data['start_time']['day_of_week']):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

					if("Fri" in compare_data['start_time']['day_of_week'])and("Fri" in schedule_data['start_time']['day_of_week']):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380)and("Sat" in compare_data['start_time']['day_of_week']):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

					if("Sat" in compare_data['start_time']['day_of_week'])and("Sat" in schedule_data['start_time']['day_of_week']):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380)and("Sun" in compare_data['start_time']['day_of_week']):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

					if("Sun" in compare_data['start_time']['day_of_week'])and("Sun" in schedule_data['start_time']['day_of_week']):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380)and("Mon" in compare_data['start_time']['day_of_week']):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

					if(compare_day_type != "custom"):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

					elif(day_type != "custom"):
						if(compare_start_time >= start_time)and(compare_start_time <= end_time):
							print("Conflict Detected.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + ". Please review and fix schedule.   \n"
						elif(overnight == True)and(compare_start_time <= end_time - 1380):
							print("Conflict Detected; Next day.")
							conflict_found = True
							conflict_msg = conflict_msg + " ! Conflict detected between " + compare_name + " and " + schedule_name + "; Time conflict where schedule runs overnight. Please review and fix schedule.   \n"

	return(conflict_found, conflict_msg)

if __name__ == '__main__':
	if is_raspberry_pi():
		app.run(host='0.0.0.0')
	else:
		app.run(host='0.0.0.0',debug=True) # Use this instead of the above line for debug mode
