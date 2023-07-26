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
import json
import requests
from geopy.geocoders import Nominatim
from common import ReadJSON, WriteJSON, WriteLog

def CheckCurrentWx(wx_data, wx_status):
	# *****************************************
	# Function: CheckWx
	# Input: str lat, str long, str api_key
	# Output: float amount (persipitation inches)
	# Description:  Get weather data for location
	# *****************************************
	lat = wx_data['lat']
	long = wx_data['long'] 
	wx_api_key = wx_data['apikey']
	history_hours = wx_data['history_hours']

	try:
		# Set Update Date / Time String 
		now = str(datetime.datetime.now())
		now = now[0:19] # Truncate the microseconds
		wx_status['updated'] = now 

		# Get Current Weather Data
		url = f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={long}&appid={wx_api_key}'
		if wx_data['units'] == 'F':
			url += '&units=imperial'
		print(f'  {url}')
		r = requests.get(url)
		parsed_json = json.loads(r.text)

		# If something went wrong with the request
		if('message' in parsed_json):
			wx_status['summary'] = parsed_json['message']
			wx_status['icon'] = '/static/img/wx-icons/unknown.png'
			wx_status['rain_current'] = 0.0
			wx_status['rain_history_list'] = []
			wx_status['rain_history_total'] = 0.0
			wx_status['temp_current'] = 0
			wx_status['last_rain_update'] = int(time.time())
			return(wx_status)

		# Get Current Temperature
		if('main' in parsed_json):
			wx_status['temp_current'] = int(parsed_json['main']['temp'])
		else:
			wx_status['temp_current'] = 0

		# Get current weather summary and icon
		if('weather' in parsed_json):
			wx_status['summary'] = parsed_json['weather'][0]['main']
			icon = parsed_json['weather'][0]['icon']
		else:
			wx_status['summary'] = "No Summary."
			icon = "00x"

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
			wx_status['icon'] = "/static/img/wx-icons/" + possible_icons[icon]
		else:
			wx_status['icon'] = "/static/img/wx-icons/unknown.png"

		# If rain in the last hour, get rain amount
		amount = 0.0
		if('rain' in parsed_json):
			amount = float(parsed_json['rain']['1h'])
			if amount > 0 and wx_data['units'] == 'F':
				# Convert mm to inches
				amount = round(amount * 0.0393701, 2)
			elif amount > 0:
				amount = round(amount, 2)
		
		wx_status['rain_current'] = amount

		# Check last time we updated the rain amount
		if('dt' in parsed_json):
			# Check if there has been a large gap (>3 hours) since the last check and clear queue if needed
			if int(parsed_json['dt']) > (wx_status['last_rain_update'] + (3 * 3600)):
				wx_status['rain_history_list'] = []
				wx_status['rain_history_list'].append(amount)
				wx_status['last_rain_update'] = int(parsed_json['dt'])

			# Check if 1h+ has passed since last storing the rain_amount
			if int(parsed_json['dt']) > (wx_status['last_rain_update'] + 3660):
				wx_status['last_rain_update'] = int(parsed_json['dt']) 
				wx_status['rain_history_list'].insert(0, amount)
				if len(wx_status['rain_history_list']) > history_hours:
					wx_status['rain_history_list'].pop()

			wx_status['rain_history_total'] = calculate_rain_history(wx_status['rain_history_list'])

	except:
		wx_status['summary'] = "Oops! Weather Lookup Error."
		wx_status['icon'] = '/static/img/wx-icons/unknown.png'
		wx_status['rain_current'] = 0.0
		wx_status['rain_history_list'] = []
		wx_status['rain_history_total'] = 0.0
		wx_status['temp_current'] = 0
		wx_status['dt'] = int(time.time())

	return wx_status

def CheckForecast(wx_data):
	# *****************************************
	# Function: CheckWx
	# Input: str lat, str long, str api_key, int hours
	# Output: float amount in inches
	# Description:  Get weather forecast for location
	# *****************************************
	lat = wx_data['lat']
	long = wx_data['long'] 
	wx_api_key = wx_data['apikey']
	forecast_hours = wx_data['forecast_hours']
	amount = 0.0
	
	try:
		# For a 4-day forecast
		# https://api.openweathermap.org/data/2.5/forecast?lat=38.6785&lon=-121.2258&appid={APIKEY}
		url = f'https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={long}&appid={wx_api_key}'
		if wx_data['units'] == 'F':
			url += '&units=imperial'
		print(f'  {url}')
		r = requests.get(url)
		parsed_json = json.loads(r.text)

		# If an error occurs, return 0
		if 'cod' in parsed_json:
			if parsed_json['cod'] == 401:
				return 0.0

		# Get forecast list
		if 'list' in parsed_json:
			if forecast_hours < 3:
				forecast_hours = 3
			if forecast_hours > 96:
				forecast_hours = 96
			hours = forecast_hours // 3
			if hours <= len(parsed_json['list']):
				for item in range(hours):
					if 'rain' in parsed_json['list'][item]:
						amount += float(parsed_json['list'][item]['rain']['3h'])

				if amount > 0 and wx_data['units'] == 'F':
					# Convert mm to inches
					amount = amount * 0.0393701

		forecast_rain = round(amount, 2)

	except:
		forecast_rain = 0.0
		print('Oops! Weather Forecast Lookup Error.')
		raise

	return forecast_rain

def calculate_rain_history(rain_history_list):
	amount = 0.0

	for hour_amount in range(len(rain_history_list)):
		amount += rain_history_list[hour_amount]

	return round(amount, 2) 

def main():
    # *****************************************************
	# Main Program
	# *****************************************************

	#Read irrigator.json
	irrigator = ReadJSON('irrigator.json')
	wx_status = ReadJSON('wx_status.json', type='weather')

	#Load location
	location = irrigator['wx_data']['location']

	try:
		geolocator = Nominatim(user_agent="irrigator")
		details = geolocator.geocode(location, timeout=None)  # Added timeout=None to prevent timeout errors
		irrigator['wx_data']['lat'] = str(details.latitude)
		irrigator['wx_data']['long'] = str(details.longitude)
		WriteJSON(irrigator, "irrigator.json")  # Update Lat/Long in weather data settings

	except:
		event = "Error getting data from Geolocator, using stored Lat/Long instead."
		WriteLog(event)

	wx_data = irrigator['wx_data']

	#Get Current Weather Data
	print(f'- Checking Current Weather.')
	# Set the number of hours to keep a record of for rain/precipitation 
	wx_status = CheckCurrentWx(wx_data, wx_status)

	#Get Forecast Weather Data
	if wx_data['forecast_enable']:
		print(f'- Checking Forecast for {wx_data["forecast_hours"]} hours in the future.')
		rain_forecast = CheckForecast(wx_data)
	else:
		rain_forecast = 0.0

	wx_status['rain_forecast'] = rain_forecast

	#Write weather.json
	WriteJSON(wx_status, 'wx_status.json')

	print(f"- Fetched Data:")
	print(f"	Location address: {wx_data['location']}")
	print(f"	Latitude:    {wx_data['lat']}")
	print(f"	Longitude:   {wx_data['long']}")
	print(f"	Conditions:  {wx_status['summary']}")
	print(f"	Icon:        {wx_status['icon']}")
	print(f"	Temperature: {wx_status['temp_current']}\u00b0{wx_data['units']}")
	print(f"	Precipitation Current: {wx_status['rain_current']}")
	print(f"	Precipitation History ({len(wx_status['rain_history_list'])}hrs): {wx_status['rain_history_total']}")
	print(f"	Precipitation Forecast({wx_data['forecast_hours']}hrs): {wx_status['rain_forecast']}")
	print(f"	Unix Time:   {wx_status['last_rain_update']}  Updated Time: {wx_status['updated']}")

if __name__ == "__main__":
    main()
