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
from datetime import datetime
import json
import requests
from geopy.geocoders import Nominatim
from common import ReadJSON, WriteJSON, WriteLog

def get_rain_history(wx_data):
	"""
	Calculates the rain history for a given location and time period.

	:param wx_data: A dictionary containing the weather data.
	:type wx_data: dict
	:return: The rain history for the given location and time period.
	:rtype: float
	"""
	lat = wx_data['lat']
	long = wx_data['long'] 
	wx_api_key = wx_data['apikey']
	history_days = wx_data['history_days']
	amount = 0.0
	year_month = datetime.today().strftime('%Y-%m')
	day = int(datetime.today().strftime('%d'))
	
	try:
		for index in range(history_days):
			date = f'{year_month}-{day - (index+1)}'
			url = f'https://api.openweathermap.org/data/3.0/onecall/day_summary?lat={lat}&lon={long}&date={date}&appid={wx_api_key}'

			if wx_data['units'] == 'F':
				url += '&units=imperial'
			print(f'  {url}')

			r = requests.get(url)
			parsed_json = json.loads(r.text)
			#print(f'  {parsed_json}')

			# If an error occurs, return 0
			if 'cod' in parsed_json:
				if parsed_json['cod'] == 401:
					print(f'ERROR Retrieving History Data: {parsed_json["cod"]} {parsed_json["message"]}')
					return 0.0

			if 'precipitation' in parsed_json:
				amount += parsed_json['precipitation']['total']

		if amount > 0 and wx_data['units'] == 'F':
			# Convert mm to inches
			amount = amount * 0.0393701

		rain_history = round(amount, 2) # Round to 2 decimal places

	except:
		rain_history = 0.0
		print('Oops! Weather Forecast Lookup Error.')
		raise

	return rain_history

def get_current_forecast(wx_data, wx_status={}):
	"""
	Retrieves current weather conditions and forecast for a given location.

	:param wx_data: A dictionary containing the latitude, longitude, and API key for the location.
	:type wx_data: dict
	:param wx_status: A dictionary containing the current weather status. Default is an empty dictionary.
	:type wx_status: dict, optional
	:return: A dictionary containing the current weather status, including the temperature, weather summary, icon, rain amount, and rain forecast.
	:rtype: dict
	"""
	lat = wx_data['lat']
	long = wx_data['long'] 
	wx_api_key = wx_data['apikey']
	forecast_days = wx_data['forecast_days']

	try:
		# Set Update Date / Time String 
		wx_status['updated'] = datetime.today().strftime('%Y-%m-%d %H:%M')
		wx_status['dt'] = int(time.time())
		
		# Get Current Weather Data
		url = f'https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={long}&appid={wx_api_key}'
		if wx_data['units'] == 'F':
			url += '&units=imperial'
		print(f'  {url}')
		r = requests.get(url)
		parsed_json = json.loads(r.text)
		#print(f'  {parsed_json}')

		# If something went wrong with the request
		if('message' in parsed_json):
			wx_status['summary'] = parsed_json['message']
			wx_status['icon'] = '/static/img/wx-icons/unknown.png'
			wx_status['rain_current'] = 0.0
			wx_status['rain_history_list'] = []
			wx_status['rain_history_total'] = 0.0
			wx_status['temp_current'] = 0
			return(wx_status)

		# Get Current Temperature
		if('current' in parsed_json):
			wx_status['temp_current'] = int(parsed_json['current']['temp'])
		else:
			wx_status['temp_current'] = 0

		# Get current weather summary and icon
		if('weather' in parsed_json['current']):
			wx_status['summary'] = parsed_json['current']['weather'][0]['main']
			icon = parsed_json['current']['weather'][0]['icon']
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
		if('rain' in parsed_json['current']):
			amount = float(parsed_json['current']['rain']['1h'])
			if amount > 0 and wx_data['units'] == 'F':
				# Convert mm to inches
				amount = round(amount * 0.0393701, 2)
			elif amount > 0:
				amount = round(amount, 2)
		
		wx_status['rain_current'] = amount

		if('daily' in parsed_json):
			# Get rain forecast (daily)
			amount = 0.0
			for day in range(forecast_days):
				if('rain' in parsed_json['daily'][day]):
					amount += float(parsed_json['daily'][day]['rain'])

			if amount > 0 and wx_data['units'] == 'F':
				# Convert mm to inches
				amount = round(amount * 0.0393701, 2)
			elif amount > 0:
				amount = round(amount, 2)
			wx_status['rain_forecast'] = amount

	except:
		wx_status['summary'] = "Oops! Weather Lookup Error."
		wx_status['icon'] = '/static/img/wx-icons/unknown.png'
		wx_status['rain_current'] = 0.0
		wx_status['rain_forecast'] = 0.0
		wx_status['temp_current'] = 0

	return wx_status


def main():
	"""
	The main program that reads the irrigator.json file, retrieves the current weather and forecast data,
	and writes the weather status to the wx_status.json file.

	:return: None
	"""
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
	print(f'\n- Checking Current Weather & Forecast.')
	# Set the number of hours to keep a record of for rain/precipitation 
	wx_status = get_current_forecast(wx_data, wx_status)

	#Get Historical Weather Data
	if wx_data['history_enable']:
		print(f'\n- Checking History for {wx_data["history_days"]} days in the past.')
		rain_history = get_rain_history(wx_data)
	else:
		rain_history = 0.0

	wx_status['rain_history_total'] = rain_history

	#Write weather.json
	WriteJSON(wx_status, 'wx_status.json')

	print(f"\n- Fetched Data:")
	print(f"	Location address: {wx_data['location']}")
	print(f"	Latitude:    {wx_data['lat']}")
	print(f"	Longitude:   {wx_data['long']}")
	print(f"	Conditions:  {wx_status['summary']}")
	print(f"	Icon:        {wx_status['icon']}")
	print(f"	Temperature: {wx_status['temp_current']}\u00b0{wx_data['units']}")
	print(f"	Precipitation Current: {wx_status['rain_current']}")
	print(f"	Precipitation History ({wx_data['history_days']}days): {wx_status['rain_history_total']}")
	print(f"	Precipitation Forecast({wx_data['forecast_days']}days): {wx_status['rain_forecast']}")
	print(f"	Unix Time:   {wx_status['dt']}  Updated Time: {wx_status['updated']}")

if __name__ == "__main__":
    main()
