#!/usr/bin/env python3
"""
MQTT Bridge for Home Assistant Integration
Publishes IrriGator zone/schedule status and subscribes to commands from Home Assistant
"""

import paho.mqtt.client as mqtt
import json
import time
import os
import sys
import threading
from datetime import datetime

# Import common utilities
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ReadJSON, WriteJSON, WriteLog, CheckString

class MQTTBridge:
	"""Bridge IrriGator state to MQTT for Home Assistant integration"""
	
	def __init__(self, settings):
		"""
		Initialize MQTT bridge
		:param settings: dict with mqtt configuration (server, port, username, password, topic_prefix, enabled)
		"""
		self.settings = settings
		self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="irrigator")
		self.client.on_connect = self.on_connect
		self.client.on_message = self.on_message
		self.client.on_disconnect = self.on_disconnect
		self.running = True
		self.last_published = {}  # Track last published state to avoid redundant publishes
		
		# Set up authentication if provided
		if settings.get('username'):
			self.client.username_pw_set(
				settings.get('username', ''),
				settings.get('password', '')
			)
	
	def on_connect(self, client, userdata, flags, rc):
		"""Callback for when client connects to broker"""
		if rc == 0:
			WriteLog(f"MQTT: Connected to broker at {self.settings['server']}:{self.settings['port']}")
			
			# Update last_connected timestamp in irrigator.json
			try:
				json_data = ReadJSON()
				json_data['mqtt']['last_connected'] = datetime.now().isoformat()
				WriteJSON(json_data)
			except Exception as e:
				WriteLog(f"MQTT: Failed to update last_connected: {str(e)}")
			
			# Subscribe to zone and schedule command topics
			prefix = self.settings.get('topic_prefix', 'irrigator')
			
			# Get list of zones and schedules from irrigator.json
			try:
				json_data = ReadJSON()
				
				# Subscribe to all zone command topics
				for zone_name in json_data.get('zonemap', {}).keys():
					topic = f"{prefix}/zone/{zone_name}/run"
					self.client.subscribe(topic)
					WriteLog(f"MQTT: Subscribed to {topic}")
				
				# Subscribe to all schedule command topics
				for schedule_name in json_data.get('schedules', {}).keys():
					topic = f"{prefix}/schedule/{schedule_name}/run"
					self.client.subscribe(topic)
					WriteLog(f"MQTT: Subscribed to {topic}")
			except Exception as e:
				WriteLog(f"MQTT: Error subscribing to topics: {str(e)}")
		else:
			WriteLog(f"MQTT: Failed to connect. Return code {rc}")
	
	def on_disconnect(self, client, userdata, rc):
		"""Callback for when client disconnects from broker"""
		if rc != 0:
			WriteLog(f"MQTT: Unexpected disconnection. Return code {rc}")
		else:
			WriteLog("MQTT: Disconnected from broker")
	
	def on_message(self, client, userdata, msg):
		"""Callback for when message is received on subscribed topic"""
		try:
			WriteLog(f"MQTT: Message received on {msg.topic}")
			payload_str = msg.payload.decode('utf-8')
			
			# Parse topic: prefix/zone/zone_name/run or prefix/schedule/schedule_name/run
			parts = msg.topic.split('/')
			prefix = self.settings.get('topic_prefix', 'irrigator')
			
			if len(parts) >= 4 and parts[0] == prefix:
				entity_type = parts[1]  # 'zone' or 'schedule'
				entity_name = '/'.join(parts[2:-1])  # Handle names with slashes (unlikely but safe)
				action = parts[-1]  # 'run'
				
				if action == 'run':
					self.handle_command(entity_type, entity_name, payload_str)
		except Exception as e:
			WriteLog(f"MQTT: Error processing message: {str(e)}")
	
	def handle_command(self, entity_type, entity_name, payload_str):
		"""
		Handle incoming MQTT command to run a zone or schedule
		:param entity_type: 'zone' or 'schedule'
		:param entity_name: name of zone or schedule
		:param payload_str: JSON payload (for zones: {"duration": minutes}, for schedules: {})
		"""
		try:
			# Read current state
			json_data = ReadJSON()
			
			# Check if system is already active
			if json_data['controls']['active']:
				error_msg = f"System already active. Cannot run {entity_type} '{entity_name}'"
				WriteLog(f"MQTT: {error_msg}")
				
				# Publish error to error topic
				prefix = self.settings.get('topic_prefix', 'irrigator')
				error_topic = f"{prefix}/{entity_type}/{entity_name}/error"
				self.client.publish(error_topic, error_msg, retain=False)
				return
			
			# Validate entity exists
			if entity_type == 'zone':
				if entity_name not in json_data.get('zonemap', {}):
					WriteLog(f"MQTT: Zone '{entity_name}' not found")
					return
				
				# Parse duration from payload (default 10 minutes)
				duration = 10
				try:
					if payload_str.strip():
						payload_json = json.loads(payload_str)
						duration = int(payload_json.get('duration', 10))
				except:
					duration = 10
				
				# Launch control.py to run the zone
				WriteLog(f"MQTT: Triggering zone '{entity_name}' for {duration} minutes")
				execute_string = f"python3 control.py -f -z {entity_name} -d {duration} &"
				if json_data['settings']['target_sys'] != 'None':
					execute_string = f"sudo python3 control.py -f -z {entity_name} -d {duration} &"
				
				os.system(execute_string)
			
			elif entity_type == 'schedule':
				if entity_name not in json_data.get('schedules', {}):
					WriteLog(f"MQTT: Schedule '{entity_name}' not found")
					return
				
				# Launch control.py to run the schedule
				WriteLog(f"MQTT: Triggering schedule '{entity_name}'")
				execute_string = f"python3 control.py -f -s {entity_name} &"
				if json_data['settings']['target_sys'] != 'None':
					execute_string = f"sudo python3 control.py -f -s {entity_name} &"
				
				os.system(execute_string)
		
		except Exception as e:
			WriteLog(f"MQTT: Error handling {entity_type} command: {str(e)}")
	
	def publish_status(self):
		"""Read current state and publish all zone/schedule status"""
		try:
			json_data = ReadJSON()
			prefix = self.settings.get('topic_prefix', 'irrigator')
			
			# Publish zone status
			for zone_name, zone_data in json_data.get('zonemap', {}).items():
				topic = f"{prefix}/zone/{zone_name}/active"
				value = 1 if zone_data.get('active', False) else 0
				
				# Only publish if state changed to reduce broker load
				if self.last_published.get(topic) != value:
					self.client.publish(topic, value, retain=True)
					self.last_published[topic] = value
			
			# Publish schedule status
			for schedule_name, schedule_data in json_data.get('schedules', {}).items():
				topic = f"{prefix}/schedule/{schedule_name}/active"
				value = 1 if schedule_data.get('start_time', {}).get('active', False) else 0
				
				# Only publish if state changed
				if self.last_published.get(topic) != value:
					self.client.publish(topic, value, retain=True)
					self.last_published[topic] = value
		
		except Exception as e:
			WriteLog(f"MQTT: Error publishing status: {str(e)}")
	
	def connect(self):
		"""Connect to MQTT broker with retry logic"""
		max_retries = 5
		retry_delay = 5  # seconds
		
		for attempt in range(max_retries):
			try:
				WriteLog(f"MQTT: Attempting to connect to {self.settings['server']}:{self.settings['port']} (attempt {attempt + 1}/{max_retries})")
				self.client.connect(
					self.settings['server'],
					self.settings['port'],
					keepalive=60
				)
				WriteLog("MQTT: Connection initiated")
				return True
			except Exception as e:
				WriteLog(f"MQTT: Connection failed: {str(e)}")
				if attempt < max_retries - 1:
					WriteLog(f"MQTT: Retrying in {retry_delay} seconds...")
					time.sleep(retry_delay)
				else:
					WriteLog("MQTT: Max connection attempts reached")
					return False
		
		return False
	
	def run(self):
		"""Main run loop: connect, publish status periodically, handle messages"""
		# Connect to broker
		if not self.connect():
			WriteLog("MQTT: Failed to connect to broker. Exiting.")
			return
		
		# Start the network loop in a background thread
		self.client.loop_start()
		
		# Main loop: publish status every 5 seconds
		publish_interval = 5  # seconds
		last_publish_time = time.time()
		
		try:
			while self.running:
				current_time = time.time()
				
				# Publish status every 5 seconds
				if current_time - last_publish_time >= publish_interval:
					self.publish_status()
					last_publish_time = current_time
				
				time.sleep(0.5)  # Small sleep to avoid busy-waiting
		
		except KeyboardInterrupt:
			WriteLog("MQTT: Received interrupt signal")
		except Exception as e:
			WriteLog(f"MQTT: Error in main loop: {str(e)}")
		finally:
			WriteLog("MQTT: Shutting down")
			self.client.loop_stop()
			self.client.disconnect()


def main():
	"""Entry point for MQTT bridge"""
	try:
		# Read configuration
		json_data = ReadJSON()
		mqtt_settings = json_data.get('mqtt', {})
		
		# Check if MQTT is enabled
		if not mqtt_settings.get('enabled', False):
			WriteLog("MQTT: MQTT is disabled in settings. Exiting.")
			sys.exit(0)
		
		# Validate required settings
		if not mqtt_settings.get('server'):
			WriteLog("MQTT: No MQTT server configured. Exiting.")
			sys.exit(1)
		
		# Create and run bridge
		bridge = MQTTBridge(mqtt_settings)
		bridge.run()
	
	except Exception as e:
		WriteLog(f"MQTT: Fatal error: {str(e)}")
		sys.exit(1)


if __name__ == '__main__':
	main()
