#!/bin/sh

NOW=$(date +"%Y-%m-%d")
LOGFILE="/usr/local/bin/irrigator/logs/backuplog-$NOW.log"

mv /usr/local/bin/irrigator/events.log $LOGFILE
touch /usr/local/bin/irrigator/events.log
