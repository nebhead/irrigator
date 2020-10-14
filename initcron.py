#!/usr/bin/env python3

# *****************************************
# irrigator - Initialize Crontab
# *****************************************
#
# Description: Add cron entries for items
#
# 1. Add reboot script to initialize relays
#  @reboot cd /home/pi/irrigator && sudo python3 control.py -i &
#
# 2. Add monthly log cleanup
#  0 0 1 * * cd /home/pi/irrigator/logs && sh backup.sh
#
# 3. Add periodic weather check
#  */15 * * * * cd /home/pi/irrigator && sudo python3 openwx.py
#
# *****************************************
from crontab import CronTab
from common import *

def checkexists(comment_string, system_cron):
    count = 0 # Init count variable
    for count in system_cron.find_comment(comment_string):
        print(count) # Look for finding the CRON Job
    return(count)


# Main Start
system_cron = CronTab(user='root')

# Initialize Relays on Boot
command_string = "cd /home/pi/irrigator && sudo python3 control.py -i &"
comment_string = "Irrigator-Init"

if (checkexists(comment_string, system_cron)==0):
    # If not found, create it.
    entry = system_cron.new(command=command_string,comment=comment_string)
    entry.every_reboot()
    entry.enable()
    system_cron.write()

# Monthly Log Cleanup
command_string = "cd /home/pi/irrigator/logs && sh backup.sh"
comment_string = "Irrigator-Log"

if (checkexists(comment_string, system_cron)==0):
    # If not found, create it.
    entry = system_cron.new(command=command_string,comment=comment_string)
    entry.setall("0 0 1 * *")
    entry.enable()
    system_cron.write()

# Cache weather information every 15 minutes
command_string = "cd /home/pi/irrigator && sudo python3 openwx.py"
comment_string = "Irrigator-WxCache"

if (checkexists(comment_string, system_cron)==0):
    # If not found, create it.
    entry = system_cron.new(command=command_string,comment=comment_string)
    entry.minute.every(15)
    entry.enable()
    system_cron.write()

# Add schedules to the crontab
json_data_dict = ReadJSON() # This will create default schedules if none exist

for item in json_data_dict['schedules']:
    command_string = "cd /home/pi/irrigator && sudo python3 control.py -s " + item + " &"
    if (checkexists(item, system_cron)==0):
        # If not found, create it.
        entry = system_cron.new(command=command_string,comment=item)
        entry.setall(json_data_dict['schedules'][item]['start_time']['cron_string'])
        if(json_data_dict['schedules'][item]['start_time']['enabled']):
            entry.enable()
        else:
            entry.enable(False)
        system_cron.write()
