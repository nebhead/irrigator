#!/usr/bin/env python3

# *****************************************
# irrigator - Weather Caching Script
# *****************************************
#
# Description: This script caches the current 
# weather in a JSON file for the webUI and 
# control scripts
#
# Uses Python3
#  sudo apt update
#  sudo apt upgrade
#  sudo apt install python3-dev python3-pip
#
# Uses GeoPy https://pypi.org/project/geopy/
#  sudo pip3 install geopy
#
# *****************************************

import time
import datetime
import os
import json
import requests
from geopy.geocoders import Nominatim

def CheckWx(lat, long, wx_api_key):
	# *****************************************
	# Function: CheckWx
	# Input: str lat, str long, str api_key
	# Output: float amount (persipitation inches)
	# Description:  Get weather data for location
	# *****************************************
	try:
		t = int(time.time())  # Get UNIX time for current time.

		#      https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={lat}&lon={lon}&dt={time}&appid={YOUR API KEY}
		url = 'https://api.openweathermap.org/data/2.5/onecall/timemachine?lat=' + lat + '&lon=' + long + '&dt=' + str(t) + '&appid=' + wx_api_key + '&units=imperial'

		r = requests.get(url)

		#Load the API response as a JSON Object
		parsed_json = json.loads(r.text)

		#Uncomment to see full JSON response
		#print(parsed_json)

		if('message' in parsed_json):
			return(0, parsed_json['message'], "/static/img/wx-icons/unknown.png")

		tempF = parsed_json['current']['temp']

		#tempC = tempK - 273.15 # Kelvin to Celsius

		#tempF = tempC * (9/5) + 32 # Celsius to Farenheit

		tempF = int(tempF)

		conditions = parsed_json['current']['weather'][0]['main']

		icon = parsed_json['current']['weather'][0]['icon']

		possible_icons = {}

		possible_icons = {
			'01d' : 'clear-day.png',
			'01n' : 'clear-night.png',
			'02d' : 'partly-cloudy-day.png',
			'02n' : 'partly-cloudy-night.png',
			'03d' : 'partly-cloudy-day.png',
			'03n' : 'partly-cloudy-night.png',
			'04d' : 'partly-cloudy-day.png',
			'04n' : 'partly-cloudy-night.png',
			'09d' : 'rain.png',
			'09n' : 'rain.png',
			'10d' : 'rain.png',
			'10n' : 'rain.png',
			'11d' : 'rain.png',
			'11n' : 'rain.png',
			'13d' : 'snow.png',
			'13n' : 'snow.png',
			'50d' : 'fog.png',
			'50n' : 'fog.png'
			}

		if(icon in possible_icons):
			icon_url = "/static/img/wx-icons/" + possible_icons[icon]
		else:
			icon_url = "/static/img/wx-icons/unknown.png"

		weather_string = "Current Temperature: " + str(tempF) + "°F <br>" + "Summary: " + str(conditions)

		amount = 0.0

		if('hourly' in parsed_json):
			for hours in parsed_json['hourly']:
				for index_key, index_value in hours.items():
					if(index_key == 'rain'):
						if('1h' in index_value):
							amount += float(index_value['1h'])

			if amount > 0:
				# Convert mm to inches
				amount = amount * 0.0393701

	except:
		amount = 0.0
		weather_string = "Oops! Weather Lookup Error."
		icon_url = "/static/img/wx-icons/unknown.png"
		raise

	return(amount, weather_string, icon_url)

def ReadJSON(json_data_filename):
	json_data_file = open(json_data_filename, "r")
	json_data_string = json_data_file.read()
	json_data_dict = json.loads(json_data_string)
	json_data_file.close()
	return(json_data_dict)

def WriteJSON(json_data_dict, json_data_filename):
	json_data_string = json.dumps(json_data_dict)
	with open(json_data_filename, 'w') as settings_file:
	    settings_file.write(json_data_string)

# *****************************************************
# Main Program
# *****************************************************

#Read irrigator.json
irrigator = ReadJSON('irrigator.json')

#Load location
location = irrigator['wx_data']['location']

try:
	geolocator = Nominatim(user_agent="irrigator")

	print("Location address:", location)

	details = geolocator.geocode(location)

	print("Latitude and Longitude of the said address:")

	lat = str(details.latitude)
	long = str(details.longitude)

	print(lat + ', ' + long)

except:
	lat = ""
	long = ""

#Load API KEY
api_key = irrigator['wx_data']['apikey']

#Get Weather Data
rain_amount, summary, icon = CheckWx(lat, long, api_key)
print(summary)
print("Icon: " + str(icon))
print("Percipitation(24hrs):" + str(rain_amount))

now = str(datetime.datetime.now())
now = now[0:19] # Truncate the microseconds

wx_status = {}

wx_status = {
	'summary' : summary,
	'icon' : icon,
	'percipitation' : rain_amount,
	'updated' : now
}
#Write weather.json
WriteJSON(wx_status, 'wx_status.json')
