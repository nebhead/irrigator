#!/bin/sh

NOW=$(date +"%Y-%m-%d")
LOGFILE="/home/pi/irrigator/logs/backuplog-$NOW.log"

mv /home/pi/irrigator/events.log $LOGFILE
touch /home/pi/irrigator/events.log
