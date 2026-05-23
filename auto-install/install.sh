#!/usr/bin/env bash

# Automatic Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
# Run from https://raw.githubusercontent.com/nebhead/irrigator/main/auto-install/install.sh
#
# Install with this command (from your Pi):
#
# curl https://raw.githubusercontent.com/nebhead/irrigator/main/auto-install/install.sh | bash
#
# NOTE: Pre-Requisites to run Raspi-Config first.  See README.md.

SUDO=""
SUDOE=""
SUDO_KEEPALIVE_PID=""

# Determine which home directory should receive the installer log.
# If launched with sudo, prefer the original user's home.
LOG_USER="${SUDO_USER:-${USER}}"
LOG_HOME="$(getent passwd "$LOG_USER" | cut -d: -f6)"
LOG_HOME="${LOG_HOME:-$HOME}"
LOG_FILE="$LOG_HOME/irrigator-install-$(date +%Y%m%d-%H%M%S).log"

# Mirror all installer output to both terminal and log file.
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Installer log: $LOG_FILE"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S %Z')"

cleanup() {
    if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then
        kill "$SUDO_KEEPALIVE_PID" >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT

# Must be root to install
if [[ $EUID -eq 0 ]];then
    echo "You are root."
else
    echo "SUDO will be used for the install."
    # Check if sudo is installed
    if command -v sudo >/dev/null 2>&1; then
        export SUDO="sudo"
        export SUDOE="sudo -E"
    else
        echo "Please install sudo."
        exit 1
    fi

    # Authenticate once up front, then refresh sudo timestamp while installer runs.
    echo "*************************************************************************"
    echo "Please enter your sudo password to continue installation."
    echo "*************************************************************************"
    sudo -v || { echo "Failed to authenticate with sudo."; exit 1; }
    while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &
    SUDO_KEEPALIVE_PID=$!
fi

# Find the rows and columns. Will default to 80x24 if it can not be detected.
screen_size=$(stty size 2>/dev/null || echo 24 80)
rows=$(echo $screen_size | awk '{print $1}')
columns=$(echo $screen_size | awk '{print $2}')

# Divide by two so the dialogs take up half of the screen.
r=$(( rows / 2 ))
c=$(( columns / 2 ))
# If the screen is small, modify defaults
r=$(( r < 20 ? 20 : r ))
c=$(( c < 70 ? 70 : c ))

# Display the welcome dialog
whiptail --msgbox --backtitle "Welcome" --title "IrriGator Automated Installer" "This installer will transform your SBC into a connected smart-sprinkler. NOTE: This installer is intended for Raspberry Pi OS Lite Bullseye or newer." ${r} ${c}

# Starting actual steps for installation
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Setting /tmp to RAM based storage in /etc/fstab                **"
echo "**                                                                     **"
echo "*************************************************************************"
if grep -qE '^tmpfs\s+/tmp\s+tmpfs' /etc/fstab; then
    echo "/tmp tmpfs entry already exists in /etc/fstab. Skipping update."
else
    echo "tmpfs /tmp  tmpfs defaults,noatime 0 0" | $SUDO tee -a /etc/fstab > /dev/null
fi
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Update... (This could take several minutes)        **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt update
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Upgrade... (This could take several minutes)       **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt upgrade -y

# Install dependencies
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Installing Dependencies... (This could take several minutes)   **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt install python3-dev python3-pip python3-venv nginx git supervisor -y

if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    echo "Raspberry Pi 5 detected. Installing python3-rpi-lgpio."
    $SUDO apt install python3-rpi-lgpio -y
else
    $SUDO apt install python3-rpi.gpio -y
fi

# Grab project files
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Cloning Project from GitHub...                                 **"
echo "**                                                                     **"
echo "*************************************************************************"
cd /usr/local/bin
if [[ -d /usr/local/bin/irrigator ]]; then
    echo "Existing /usr/local/bin/irrigator directory found."
    echo "Please remove or rename it before running this installer."
    exit 1
fi
$SUDO git clone https://github.com/nebhead/irrigator

### Setup Python VENV and Install Python dependencies
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Setting up Python VENV and installing modules...               **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO python3 -m venv --system-site-packages /usr/local/bin/irrigator/.venv
$SUDO /usr/local/bin/irrigator/.venv/bin/pip install --upgrade pip
$SUDO /usr/local/bin/irrigator/.venv/bin/pip install -r /usr/local/bin/irrigator/auto-install/requirements.txt

# Create/update irrigator.json defaults for this fresh install so runtime
# scripts know to use the venv interpreter.
cd /usr/local/bin/irrigator
$SUDO /usr/local/bin/irrigator/.venv/bin/python - <<'PY'
from common import ReadJSON, WriteJSON

data = ReadJSON()
data.setdefault('settings', {})
data['settings']['use_venv'] = True
data['settings']['python_exec'] = '/usr/local/bin/irrigator/.venv/bin/python'
WriteJSON(data)
PY

### Setup nginx to proxy to gunicorn
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring nginx...                                           **"
echo "**                                                                     **"
echo "*************************************************************************"
# Move into install directory
cd /usr/local/bin/irrigator/auto-install/nginx

# Delete default configuration
$SUDO rm /etc/nginx/sites-enabled/default

# Copy configuration file to nginx
$SUDO cp irrigator.nginx /etc/nginx/sites-available/irrigator

# Create link in sites-enabled
$SUDO ln -s /etc/nginx/sites-available/irrigator /etc/nginx/sites-enabled

# Restart nginx
$SUDO service nginx restart

### Setup Supervisor to Start Apps on Boot / Restart on Failures
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring Supervisord...                                     **"
echo "**                                                                     **"
echo "*************************************************************************"

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
# NOTE: If you used a different directory for the installation then make sure you edit the *.conf files appropriately
cd /usr/local/bin/irrigator/auto-install/supervisor

$SUDO cp *.conf /etc/supervisor/conf.d/

SVISOR=$(whiptail --title "Would you like to enable the supervisor WebUI?" --radiolist "This allows you to check the status of the supervised processes via a web browser, and also allows those processes to be restarted directly from this interface. (Recommended)" 20 78 2 "ENABLE_SVISOR" "Enable the WebUI" ON "DISABLE_SVISOR" "Disable the WebUI" OFF 3>&1 1>&2 2>&3)

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
   echo " " | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "[inet_http_server]" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "port = 9001" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   USERNAME=$(whiptail --inputbox "Choose a username [default: user]" 8 78 user --title "Choose Username" 3>&1 1>&2 2>&3)
   echo "username = " $USERNAME | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   PASSWORD=$(whiptail --passwordbox "Enter your password" 8 78 --title "Choose Password" 3>&1 1>&2 2>&3)
   echo "password = " $PASSWORD | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   whiptail --msgbox --backtitle "Supervisor WebUI Setup" --title "Setup Completed" "You now should be able to access the Supervisor WebUI at http://your.ip.address.here:9001 with the username and password you have chosen." ${r} ${c}
else
   echo "No WebUI Setup."
fi

# If supervisor isn't already running, startup Supervisor
$SUDO service supervisor start

# Setup CRONTAB
cd /usr/local/bin/irrigator
$SUDO /usr/local/bin/irrigator/.venv/bin/python initcron.py

# Rebooting
whiptail --msgbox --backtitle "Install Complete / Reboot Required" --title "Installation Completed - Rebooting" "Congratulations, the installation is complete.  At this time, we will perform a reboot and your application should be ready.  You should be able to access your application by opening a browser on your PC or other device and using the IP address for this SBC.  Enjoy!" ${r} ${c}
clear
$SUDO reboot
