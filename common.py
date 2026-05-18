#!/usr/bin/env python3

# *****************************************
# irrigator - common functions
# *****************************************
#
# Description: This script contains common functions
#
# *****************************************

import time
import json
import datetime
import io
import re
from cron_descriptor import get_description, ExpressionDescriptor

VERSION_MANIFEST_FILENAME = "manifest.json"
DEFAULT_VERSION = "0000.00.000"
VERSION_COMPONENT_LABELS = {
    'app': 'Flask Web Application',
    'control': 'Control Application',
    'weather_api': 'Weather API Application'
}

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

    if type == 'settings':
        # Check relay trigger which was added post-initial release 
        if 'relay_trigger' not in json_data_dict['settings'].keys():
            relay_trigger = 0  # Set default to active low (0) triggered relays 
            json_data_dict['settings']['relay_trigger'] = 0  # set the default to active low (0) triggered in settings, and save
            WriteJSON(json_data_dict)
        # Check if history and forecast days are set
        if 'history_days' not in json_data_dict['wx_data']:
            json_data_dict['wx_data']['history_days'] = 2 
            json_data_dict['wx_data']['forecast_days'] = 2
            WriteJSON(json_data_dict)
            wx_data = create_wx_json()
            WriteJSON(wx_data, json_data_filename='wx_status.json')
        # Check if metadata section exists (version tracking for updates)
        if 'metadata' not in json_data_dict:
            manifest_data = ReadVersionManifest()
            current_version = manifest_data.get('global_version', DEFAULT_VERSION)
            json_data_dict['metadata'] = {
                'version': current_version,
                'last_updated': datetime.datetime.now().isoformat()
            }
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

def version_format_is_valid(version_string):
    return bool(re.match(r'^\d{4}\.\d{2}\.\d{3}$', str(version_string)))

def create_version_manifest(global_version=DEFAULT_VERSION):
    components = {}
    for component_name in VERSION_COMPONENT_LABELS:
        components[component_name] = global_version

    return {
        'global_version': global_version,
        'components': components
    }

def ReadVersionManifest(manifest_filename=VERSION_MANIFEST_FILENAME):
    try:
        with open(manifest_filename, 'r') as manifest_file:
            manifest_data = json.loads(manifest_file.read())
    except(IOError, OSError):
        event = f"Exception occurred when reading {manifest_filename}. File not found. Using default version manifest."
        WriteLog(event)
        manifest_data = create_version_manifest()
    except(ValueError):
        event = f"Exception occurred when reading {manifest_filename}. Value Error Exception - JSONDecodeError. Using default version manifest."
        WriteLog(event)
        manifest_data = create_version_manifest()

    global_version = manifest_data.get('global_version', DEFAULT_VERSION)
    if version_format_is_valid(global_version) == False:
        global_version = DEFAULT_VERSION

    components = {}
    manifest_components = manifest_data.get('components', {})
    for component_name, component_label in VERSION_COMPONENT_LABELS.items():
        component_version = manifest_components.get(component_name, global_version)
        if version_format_is_valid(component_version) == False:
            component_version = global_version
        components[component_name] = {
            'label': component_label,
            'version': component_version
        }

    return {
        'global_version': global_version,
        'components': components
    }

def GetComponentVersion(component_name, manifest_data=None):
    if manifest_data is None:
        manifest_data = ReadVersionManifest()

    component_data = manifest_data.get('components', {}).get(component_name, {})
    return component_data.get('version', manifest_data.get('global_version', DEFAULT_VERSION))

def WriteStartupVersionLog(component_name, component_label=None, manifest_data=None):
    if manifest_data is None:
        manifest_data = ReadVersionManifest()

    if component_label is None:
        component_label = VERSION_COMPONENT_LABELS.get(component_name, component_name)

    version = GetComponentVersion(component_name, manifest_data)
    event = f"***** {component_label} Starting - Version {version} *****"
    WriteLog(event)

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
        'history_days': 2,  # Number of days of history to track precipitation
        'forecast_days': 2,  # Number of days to forecast precipitation
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
        'rain_history_total' : 0,
        'rain_current' : 0,
		'rain_forecast' : 0.0,
        'temp_current' : 0,
        'dt' : int(time.time())
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


# ************************************************************
# Update System Functions
# ************************************************************

def is_git_repo():
	"""
	Check if the current directory is a git repository
	:return: True if .git directory exists, False otherwise
	"""
	import os
	return os.path.isdir('.git')

def get_local_version():
	"""
	Get the local version from irrigator.json metadata, fallback to manifest.json
	:return: version string (YYYY.MM.BBB format)
	"""
	try:
		irrigator_data = ReadJSON(json_data_filename="irrigator.json", type="settings")
		if 'metadata' in irrigator_data and 'version' in irrigator_data['metadata']:
			return irrigator_data['metadata']['version']
	except Exception as e:
		WriteLog(f"Exception getting local version from irrigator.json: {str(e)}")
	
	# Fallback to manifest
	manifest_data = ReadVersionManifest()
	return manifest_data.get('global_version', DEFAULT_VERSION)

def get_remote_commit_count():
	"""
	Get the number of commits behind origin/main
	:return: int count of commits behind, or error string if not a git repo
	"""
	if not is_git_repo():
		return {'error': 'Not a git repository'}
	
	try:
		import subprocess
		# Fetch to get latest remote info
		subprocess.run(['git', 'fetch', 'origin', 'main', '--dry-run'], 
					   capture_output=True, timeout=15)
		
		# Count commits: how many commits are on origin/main but not on HEAD
		result = subprocess.run(['git', 'rev-list', 'origin/main', '^HEAD'],
							   capture_output=True, text=True, timeout=10)
		
		if result.returncode == 0:
			lines = result.stdout.strip().split('\n')
			count = len([l for l in lines if l.strip()])
			return count
		else:
			return {'error': 'Failed to count commits: ' + result.stderr}
	except subprocess.TimeoutExpired:
		return {'error': 'Git command timed out'}
	except Exception as e:
		return {'error': f'Exception: {str(e)}'}

def get_commits_since_local():
	"""
	Get list of commits on origin/main that are not on local HEAD
	:return: list of dicts with {hash, title, body}, or error dict
	"""
	if not is_git_repo():
		return {'error': 'Not a git repository'}
	
	try:
		import subprocess
		# Fetch to get latest remote info (dry-run to avoid modifying state)
		subprocess.run(['git', 'fetch', 'origin', 'main', '--dry-run'],
					   capture_output=True, timeout=15)
		
		# Get commits: origin/main but not HEAD, with custom format
		# Format: hash|title|body (separated by |, newline between commits)
		result = subprocess.run(
			['git', 'log', 'origin/main', '^HEAD', '--pretty=format:%H|%s|%b===COMMIT_END==='],
			capture_output=True, text=True, timeout=10
		)
		
		if result.returncode != 0:
			return {'error': 'Failed to get commits: ' + result.stderr}
		
		commits = []
		commit_blocks = result.stdout.split('===COMMIT_END===')
		
		for block in commit_blocks:
			if not block.strip():
				continue
			parts = block.strip().split('|', 2)
			if len(parts) >= 2:
				commits.append({
					'hash': parts[0].strip(),
					'title': parts[1].strip(),
					'body': parts[2].strip() if len(parts) > 2 else ''
				})
		
		return commits
	except subprocess.TimeoutExpired:
		return {'error': 'Git command timed out'}
	except Exception as e:
		return {'error': f'Exception: {str(e)}'}

def perform_git_update():
	"""
	Perform git update: fetch origin/main and merge with local changes
	Uses 'git merge -X theirs' to force remote changes over local in case of conflicts
	:return: dict with {success: bool, message: str, output: str}
	"""
	if not is_git_repo():
		return {
			'success': False,
			'message': 'Not a git repository',
			'output': 'Error: .git directory not found'
		}
	
	try:
		import subprocess
		output_lines = []
		
		# Step 1: Fetch from remote
		output_lines.append('[1/3] Fetching from origin/main...')
		result = subprocess.run(['git', 'fetch', 'origin', 'main'],
							   capture_output=True, text=True, timeout=30)
		if result.returncode != 0:
			return {
				'success': False,
				'message': 'Fetch failed',
				'output': '\n'.join(output_lines) + '\nError: ' + result.stderr
			}
		output_lines.append('✓ Fetch successful')
		
		# Step 2: Merge with -X theirs strategy (remote wins on conflicts)
		output_lines.append('[2/3] Merging origin/main...')
		result = subprocess.run(['git', 'merge', '-X', 'theirs', 'origin/main'],
							   capture_output=True, text=True, timeout=30)
		if result.returncode != 0:
			return {
				'success': False,
				'message': 'Merge failed',
				'output': '\n'.join(output_lines) + '\nError: ' + result.stderr
			}
		output_lines.append('✓ Merge successful')
		
		# Step 3: Clean up any untracked files (optional, just log if any exist)
		output_lines.append('[3/3] Cleaning up...')
		result = subprocess.run(['git', 'status', '--porcelain'],
							   capture_output=True, text=True, timeout=10)
		if result.stdout.strip():
			output_lines.append('Note: Repository has local modifications after merge')
		output_lines.append('✓ Update complete')
		
		return {
			'success': True,
			'message': 'Update successful',
			'output': '\n'.join(output_lines)
		}
	except subprocess.TimeoutExpired:
		return {
			'success': False,
			'message': 'Git command timed out',
			'output': '\n'.join(output_lines) + '\nError: Command timed out'
		}
	except Exception as e:
		return {
			'success': False,
			'message': f'Exception: {str(e)}',
			'output': '\n'.join(output_lines) + f'\nError: {str(e)}'
		}

def UpdateMetadata(new_version):
	"""
	Update the version and last_updated timestamp in irrigator.json
	:param new_version: version string (YYYY.MM.BBB format)
	"""
	try:
		json_data = ReadJSON(json_data_filename="irrigator.json", type="settings")
		if 'metadata' not in json_data:
			json_data['metadata'] = {}
		json_data['metadata']['version'] = new_version
		json_data['metadata']['last_updated'] = datetime.datetime.now().isoformat()
		WriteJSON(json_data)
		WriteLog(f"Updated metadata to version {new_version}")
		return True
	except Exception as e:
		WriteLog(f"Exception updating metadata: {str(e)}")
		return False

def RunUpgradePath(old_version, new_version):
	"""
	Execute upgrade/migration logic based on version comparison
	Runs all upgrade steps between old_version and new_version in sequence
	
	:param old_version: current version (YYYY.MM.BBB format)
	:param new_version: target version (YYYY.MM.BBB format)
	:return: dict with {success: bool, message: str, details: []}
	"""
	result = {
		'success': True,
		'message': f'Upgraded from {old_version} to {new_version}',
		'details': []
	}
	
	# Parse versions for comparison
	def version_tuple(v):
		try:
			parts = v.split('.')
			return tuple(int(p) for p in parts)
		except:
			return (0, 0, 0)
	
	old_tuple = version_tuple(old_version)
	new_tuple = version_tuple(new_version)
	
	if old_tuple >= new_tuple:
		result['details'].append('Already at or ahead of target version')
		return result
	
	# List of upgrade steps by version
	# Format: (version_tuple, function, description)
	upgrade_steps = [
		# Example for future use:
		# ((2026, 5, 2), upgrade_2026_05_002, "Crontab sync"),
		# ((2026, 6, 0), upgrade_2026_06_000, "New feature setup"),
	]
	
	# Execute each upgrade step that falls between old_version and new_version
	for step_version, upgrade_func, description in upgrade_steps:
		if old_tuple < step_version <= new_tuple:
			try:
				result['details'].append(f"Running: {description}...")
				upgrade_func()
				result['details'].append(f"✓ {description} complete")
				WriteLog(f"Upgrade step {step_version}: {description} completed")
			except Exception as e:
				error_msg = f"✗ {description} failed: {str(e)}"
				result['details'].append(error_msg)
				WriteLog(f"Upgrade step {step_version}: {description} FAILED - {str(e)}")
				result['success'] = False
	
	if not result['details']:
		result['details'].append('No version-specific upgrade steps needed')
	
	return result