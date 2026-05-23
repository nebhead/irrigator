#!/usr/bin/env python3
"""
MQTT Bridge for Home Assistant Integration
Publishes IrriGator zone/schedule status and subscribes to commands from Home Assistant
"""

import json
import time
import os
import sys
import subprocess
import threading
import re
from datetime import datetime

try:
	import paho.mqtt.client as mqtt
	MQTT_IMPORT_ERROR = None
except ImportError as exc:
	mqtt = None
	MQTT_IMPORT_ERROR = exc

# Import common utilities
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ReadJSON, WriteJSON, WriteLog

DISCOVERY_ROOT = 'homeassistant'
DISCOVERY_COMPONENT = 'switch'
DISCOVERY_NODE = 'irrigator'
DISCOVERY_REFRESH_MARKER = '.mqtt_discovery_refresh'
DISCOVERY_CACHE_FILE = '.mqtt_discovery_cache.json'
DEFAULT_ZONE_DURATION_MINUTES = 10

class MQTTBridge:
	"""Bridge IrriGator state to MQTT for Home Assistant integration"""
	
	def __init__(self, settings):
		"""
		Initialize MQTT bridge
		:param settings: dict with mqtt configuration (server, port, username, password, topic_prefix, enabled)
		"""
		if mqtt is None:
			raise RuntimeError("Missing dependency 'paho-mqtt'. Install it for the system interpreter with 'sudo /usr/bin/python3 -m pip install paho-mqtt'.") from MQTT_IMPORT_ERROR

		self.settings = settings
		self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="irrigator")
		self.client.on_connect = self.on_connect
		self.client.on_message = self.on_message
		self.client.on_disconnect = self.on_disconnect
		self.running = True
		self.last_published = {}  # Track last published state to avoid redundant publishes
		self.discovery_refresh_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DISCOVERY_REFRESH_MARKER)
		self.discovery_cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DISCOVERY_CACHE_FILE)
		self.discovery_refresh_mtime = 0
		self.discovery_state = {
			'zone': set(),
			'schedule': set()
		}
		self.subscribed_command_topics = set()
		self.load_discovery_cache()

		prefix = self.settings.get('topic_prefix', 'irrigator')
		self.availability_topic = f"{prefix}/bridge/availability"
		self.client.will_set(self.availability_topic, payload='offline', retain=True)
		
		# Set up authentication if provided
		if settings.get('username'):
			self.client.username_pw_set(
				settings.get('username', ''),
				settings.get('password', '')
			)

	def sanitize_for_id(self, raw_value):
		"""Convert names to stable IDs suitable for MQTT discovery topics and unique IDs."""
		safe = re.sub(r'[^A-Za-z0-9_]', '_', str(raw_value))
		safe = re.sub(r'_+', '_', safe).strip('_').lower()
		if safe == '':
			return 'unnamed'
		return safe

	def get_discovery_topic(self, entity_type, entity_name):
		safe_name = self.sanitize_for_id(entity_name)
		return f"{DISCOVERY_ROOT}/{DISCOVERY_COMPONENT}/{DISCOVERY_NODE}/{entity_type}_{safe_name}/config"

	def load_discovery_cache(self):
		"""Load previously published discovery entity names to allow cleanup after restart."""
		try:
			with open(self.discovery_cache_path, 'r') as cache_file:
				cache_data = json.load(cache_file)
			self.discovery_state['zone'] = set(cache_data.get('zone', []))
			self.discovery_state['schedule'] = set(cache_data.get('schedule', []))
		except:
			self.discovery_state['zone'] = set()
			self.discovery_state['schedule'] = set()

	def save_discovery_cache(self):
		"""Persist published discovery entities so deletions can be reconciled after restart."""
		try:
			cache_data = {
				'zone': sorted(list(self.discovery_state['zone'])),
				'schedule': sorted(list(self.discovery_state['schedule']))
			}
			with open(self.discovery_cache_path, 'w') as cache_file:
				json.dump(cache_data, cache_file)
		except Exception as e:
			WriteLog(f"MQTT-Discovery: Failed to save discovery cache: {str(e)}")

	def build_device_payload(self):
		"""Shared Home Assistant device metadata for all discovered entities."""
		return {
			'identifiers': ['irrigator_system'],
			'name': 'IrriGator',
			'manufacturer': 'IrriGator',
			'model': 'Sprinkler Controller'
		}

	def build_discovery_payload(self, entity_type, entity_name, prefix):
		"""Build a Home Assistant discovery payload for a zone or schedule switch."""
		safe_name = self.sanitize_for_id(entity_name)
		unique_id = f"irrigator_{entity_type}_{safe_name}"
		icon = 'mdi:sprinkler' if entity_type == 'zone' else 'mdi:calendar-clock'
		entity_label = 'Zone' if entity_type == 'zone' else 'Schedule'

		return {
			'name': f"{entity_name}",
			'object_id': unique_id,
			'unique_id': unique_id,
			'command_topic': f"{prefix}/{entity_type}/{entity_name}/set",
			'state_topic': f"{prefix}/{entity_type}/{entity_name}/active",
			'payload_on': 'ON',
			'payload_off': 'OFF',
			'state_on': '1',
			'state_off': '0',
			'availability_topic': self.availability_topic,
			'payload_available': 'online',
			'payload_not_available': 'offline',
			'icon': icon,
			'device': self.build_device_payload(),
			'origin': {
				'name': f'IrriGator {entity_label} MQTT Discovery'
			}
		}

	def publish_discovery_entity(self, entity_type, entity_name, prefix):
		"""Publish retained discovery config for a single entity."""
		discovery_topic = self.get_discovery_topic(entity_type, entity_name)
		payload = self.build_discovery_payload(entity_type, entity_name, prefix)
		self.client.publish(discovery_topic, json.dumps(payload), retain=True)
		WriteLog(f"MQTT-Discovery: Published {entity_type} entity '{entity_name}' to {discovery_topic}")

	def publish_discovery_cleanup(self, entity_type, entity_name):
		"""Remove an entity from Home Assistant by publishing an empty retained config."""
		discovery_topic = self.get_discovery_topic(entity_type, entity_name)
		self.client.publish(discovery_topic, payload='', retain=True)
		WriteLog(f"MQTT-Discovery: Removed stale {entity_type} entity '{entity_name}' from {discovery_topic}")

	def sync_command_subscriptions(self, json_data):
		"""Subscribe/unsubscribe command topics so runtime control matches current JSON entities."""
		prefix = self.settings.get('topic_prefix', 'irrigator')
		target_topics = set()

		for zone_name in json_data.get('zonemap', {}).keys():
			target_topics.add(f"{prefix}/zone/{zone_name}/run")
			target_topics.add(f"{prefix}/zone/{zone_name}/set")

		for schedule_name in json_data.get('schedules', {}).keys():
			target_topics.add(f"{prefix}/schedule/{schedule_name}/run")
			target_topics.add(f"{prefix}/schedule/{schedule_name}/set")

		for topic in (self.subscribed_command_topics - target_topics):
			self.client.unsubscribe(topic)
			WriteLog(f"MQTT: Unsubscribed from {topic}")

		for topic in (target_topics - self.subscribed_command_topics):
			self.client.subscribe(topic)
			WriteLog(f"MQTT: Subscribed to {topic}")

		self.subscribed_command_topics = target_topics

	def sync_discovery(self, force_republish=False):
		"""Publish discovery for current entities and cleanup deleted ones."""
		try:
			json_data = ReadJSON()
			prefix = self.settings.get('topic_prefix', 'irrigator')
			self.sync_command_subscriptions(json_data)

			current_zone_names = set(json_data.get('zonemap', {}).keys())
			current_schedule_names = set(json_data.get('schedules', {}).keys())

			removed_zones = self.discovery_state['zone'] - current_zone_names
			removed_schedules = self.discovery_state['schedule'] - current_schedule_names

			for removed_zone in removed_zones:
				self.publish_discovery_cleanup('zone', removed_zone)
			for removed_schedule in removed_schedules:
				self.publish_discovery_cleanup('schedule', removed_schedule)

			for zone_name in current_zone_names:
				if force_republish or (zone_name not in self.discovery_state['zone']):
					self.publish_discovery_entity('zone', zone_name, prefix)

			for schedule_name in current_schedule_names:
				if force_republish or (schedule_name not in self.discovery_state['schedule']):
					self.publish_discovery_entity('schedule', schedule_name, prefix)

			self.discovery_state['zone'] = current_zone_names
			self.discovery_state['schedule'] = current_schedule_names
			self.save_discovery_cache()
		except Exception as e:
			WriteLog(f"MQTT-Discovery: Failed to synchronize discovery topics: {str(e)}")

	def refresh_discovery_if_signaled(self):
		"""Watch for app-triggered marker updates and republish discovery as needed."""
		try:
			marker_mtime = os.path.getmtime(self.discovery_refresh_path)
		except OSError:
			return

		if marker_mtime > self.discovery_refresh_mtime:
			self.discovery_refresh_mtime = marker_mtime
			WriteLog('MQTT-Discovery: Refresh marker changed; syncing discovery topics')
			self.sync_discovery(force_republish=False)

	def stop_active_run(self, entity_type, entity_name):
		"""Signal control loop to stop the currently running zone or schedule."""
		try:
			json_data = ReadJSON()
			if json_data['controls'].get('active', False):
				json_data['controls']['manual_override'] = True
				WriteJSON(json_data)
				WriteLog(f"MQTT: Stop command requested for {entity_type} '{entity_name}'")
			else:
				WriteLog(f"MQTT: Stop command ignored for {entity_type} '{entity_name}' because system is inactive")
		except Exception as e:
			WriteLog(f"MQTT: Failed to process stop command for {entity_type} '{entity_name}': {str(e)}")

	def handle_switch_command(self, entity_type, entity_name, payload_str):
		"""Handle Home Assistant switch ON/OFF commands received on .../set topics."""
		payload_value = str(payload_str).strip()
		payload_normalized = payload_value.upper()

		if payload_value.startswith('{'):
			try:
				payload_json = json.loads(payload_value)
				payload_normalized = str(payload_json.get('state', payload_json.get('value', payload_value))).upper()
			except:
				pass

		if payload_normalized in ['ON', '1', 'TRUE']:
			if entity_type == 'zone':
				self.handle_command(entity_type, entity_name, '', forced_duration=DEFAULT_ZONE_DURATION_MINUTES)
			elif entity_type == 'schedule':
				self.handle_command(entity_type, entity_name, '{}', forced_duration=None)
			else:
				WriteLog(f"MQTT: Unsupported switch entity type '{entity_type}'")
		elif payload_normalized in ['OFF', '0', 'FALSE']:
			self.stop_active_run(entity_type, entity_name)
		else:
			WriteLog(f"MQTT: Unsupported switch payload '{payload_value}' for {entity_type} '{entity_name}'")
	
	def on_connect(self, client, userdata, flags, rc):
		"""Callback for when client connects to broker"""
		if rc == 0:
			WriteLog(f"MQTT: Connected to broker at {self.settings['server']}:{self.settings['port']}")
			self.client.publish(self.availability_topic, payload='online', retain=True)
			
			# Update last_connected timestamp in irrigator.json
			try:
				json_data = ReadJSON()
				json_data['mqtt']['last_connected'] = datetime.now().isoformat()
				WriteJSON(json_data)
			except Exception as e:
				WriteLog(f"MQTT: Failed to update last_connected: {str(e)}")
			
			# Reconcile command subscriptions and discovery entities from irrigator.json
			try:
				json_data = ReadJSON()
				self.sync_discovery(force_republish=True)
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
			
			# Parse topic: prefix/zone/zone_name/run|set or prefix/schedule/schedule_name/run|set
			parts = msg.topic.split('/')
			prefix = self.settings.get('topic_prefix', 'irrigator')
			
			if len(parts) >= 4 and parts[0] == prefix:
				entity_type = parts[1]  # 'zone' or 'schedule'
				entity_name = '/'.join(parts[2:-1])  # Handle names with slashes (unlikely but safe)
				action = parts[-1]  # 'run'
				
				if action == 'run':
					self.handle_command(entity_type, entity_name, payload_str)
				elif action == 'set':
					self.handle_switch_command(entity_type, entity_name, payload_str)
		except Exception as e:
			WriteLog(f"MQTT: Error processing message: {str(e)}")
	
	def handle_command(self, entity_type, entity_name, payload_str, forced_duration=None):
		"""
		Handle incoming MQTT command to run a zone or schedule
		:param entity_type: 'zone' or 'schedule'
		:param entity_name: name of zone or schedule
		:param payload_str: JSON payload (for zones: {"duration": minutes}, for schedules: {})
		:param forced_duration: Optional fixed duration for zone runs (used by switch ON commands)
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
				duration = DEFAULT_ZONE_DURATION_MINUTES
				if forced_duration is not None:
					duration = int(forced_duration)
				else:
					try:
						if payload_str.strip():
							payload_json = json.loads(payload_str)
							duration = int(payload_json.get('duration', DEFAULT_ZONE_DURATION_MINUTES))
					except:
						duration = DEFAULT_ZONE_DURATION_MINUTES
				
				# Launch control.py to run the zone
				WriteLog(f"MQTT: Triggering zone '{entity_name}' for {duration} minutes")
				command = ['python3', 'control.py', '-f', '-z', entity_name, '-d', str(duration)]
				if json_data['settings']['target_sys'] != 'None':
					command.insert(0, 'sudo')

				subprocess.Popen(command)
			
			elif entity_type == 'schedule':
				if entity_name not in json_data.get('schedules', {}):
					WriteLog(f"MQTT: Schedule '{entity_name}' not found")
					return
				
				# Launch control.py to run the schedule
				WriteLog(f"MQTT: Triggering schedule '{entity_name}'")
				command = ['python3', 'control.py', '-f', '-s', entity_name]
				if json_data['settings']['target_sys'] != 'None':
					command.insert(0, 'sudo')

				subprocess.Popen(command)
		
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
		refresh_check_interval = 2  # seconds
		last_refresh_check_time = time.time()
		
		try:
			while self.running:
				current_time = time.time()
				
				# Publish status every 5 seconds
				if current_time - last_publish_time >= publish_interval:
					self.publish_status()
					last_publish_time = current_time

				if current_time - last_refresh_check_time >= refresh_check_interval:
					self.refresh_discovery_if_signaled()
					last_refresh_check_time = current_time
				
				time.sleep(0.5)  # Small sleep to avoid busy-waiting
		
		except KeyboardInterrupt:
			WriteLog("MQTT: Received interrupt signal")
		except Exception as e:
			WriteLog(f"MQTT: Error in main loop: {str(e)}")
		finally:
			WriteLog("MQTT: Shutting down")
			self.client.publish(self.availability_topic, payload='offline', retain=True)
			self.client.loop_stop()
			self.client.disconnect()


def main():
	"""Entry point for MQTT bridge"""
	try:
		if mqtt is None:
			WriteLog("MQTT: Missing dependency 'paho-mqtt'. Install it for the system interpreter with 'sudo /usr/bin/python3 -m pip install paho-mqtt'.")
			sys.exit(1)

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
