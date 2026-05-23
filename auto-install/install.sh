#!/usr/bin/env bash

set -Eeuo pipefail

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

log_command() {
    echo
    echo "[COMMAND] $*"
    set +e
    "$@" 2>&1 | tee -a "$LOG_FILE"
    local rc=${PIPESTATUS[0]}
    set -e
    if [[ $rc -ne 0 ]]; then
        log_note "ERROR: Command failed with exit code ${rc}: $*"
    fi
    return $rc
}

log_note() {
    echo "$*" | tee -a "$LOG_FILE"
}

on_error() {
    local exit_code="$?"
    local line_no="$1"
    local failed_command="$2"

    log_note "ERROR: Command failed with exit code ${exit_code} at line ${line_no}: ${failed_command}"
    log_note "Installation aborted. Review installer log: ${LOG_FILE}"
    exit "${exit_code}"
}

banner() {
    log_note "*************************************************************************"
    log_note "**                                                                     **"
    log_note "**      $1"
    log_note "**                                                                     **"
    log_note "*************************************************************************"
}

log_note "Installer log: $LOG_FILE"
log_note "Started: $(date '+%Y-%m-%d %H:%M:%S %Z')"

trap 'on_error "$LINENO" "$BASH_COMMAND"' ERR

cleanup() {
    if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then
        kill "$SUDO_KEEPALIVE_PID" >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT

# Must be root to install
if [[ $EUID -eq 0 ]];then
    log_note "You are root."
else
    log_note "SUDO will be used for the install."
    # Check if sudo is installed
    if command -v sudo >/dev/null 2>&1; then
        export SUDO="sudo"
        export SUDOE="sudo -E"
    else
        log_note "Please install sudo."
        exit 1
    fi

    # Authenticate once up front, then refresh sudo timestamp while installer runs.
    log_note "*************************************************************************"
    log_note "Please enter your sudo password to continue installation."
    log_note "*************************************************************************"
    sudo -v || { log_note "Failed to authenticate with sudo."; exit 1; }
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
banner "Setting /tmp to RAM based storage in /etc/fstab"
if grep -qE '^tmpfs\s+/tmp\s+tmpfs' /etc/fstab; then
    log_note "/tmp tmpfs entry already exists in /etc/fstab. Skipping update."
else
    log_command $SUDO tee -a /etc/fstab > /dev/null <<<'tmpfs /tmp  tmpfs defaults,noatime 0 0'
fi
banner "Running Apt Update... (This could take several minutes)"
log_command $SUDO apt update
banner "Running Apt Upgrade... (This could take several minutes)"
log_command $SUDO apt upgrade -y

# Install dependencies
banner "Installing Dependencies... (This could take several minutes)"
log_command $SUDO apt install python3-dev python3-pip python3-venv nginx git supervisor -y

if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    log_note "Raspberry Pi 5 detected. Installing python3-rpi-lgpio."
    log_command $SUDO apt install python3-rpi-lgpio -y
else
    log_command $SUDO apt install python3-rpi.gpio -y
fi

# Grab project files
banner "Cloning Project from GitHub..."
cd /usr/local/bin
if [[ -d /usr/local/bin/irrigator ]]; then
    log_note "Existing /usr/local/bin/irrigator directory found."
    log_note "Please remove or rename it before running this installer."
    exit 1
fi
log_command $SUDO git clone https://github.com/nebhead/irrigator

### Setup Python VENV and Install Python dependencies
banner "Setting up Python VENV and installing modules..."
log_command $SUDO python3 -m venv --system-site-packages /usr/local/bin/irrigator/.venv
log_command $SUDO /usr/local/bin/irrigator/.venv/bin/pip install --upgrade pip
log_command $SUDO /usr/local/bin/irrigator/.venv/bin/pip install -r /usr/local/bin/irrigator/auto-install/requirements.txt

# Create/update irrigator.json defaults for this fresh install so runtime
# scripts know to use the venv interpreter.
cd /usr/local/bin/irrigator
log_command $SUDO /usr/local/bin/irrigator/.venv/bin/python - <<'PY'
from common import ReadJSON, WriteJSON

data = ReadJSON()
data.setdefault('settings', {})
data['settings']['use_venv'] = True
data['settings']['python_exec'] = '/usr/local/bin/irrigator/.venv/bin/python'
WriteJSON(data)
PY

### Setup nginx to proxy to gunicorn
banner "Configuring nginx..."
# Move into install directory
cd /usr/local/bin/irrigator/auto-install/nginx

# Delete default configuration
log_command $SUDO rm /etc/nginx/sites-enabled/default

# Copy configuration file to nginx
log_command $SUDO cp irrigator.nginx /etc/nginx/sites-available/irrigator

# Create link in sites-enabled
log_command $SUDO ln -s /etc/nginx/sites-available/irrigator /etc/nginx/sites-enabled

# Restart nginx
log_command $SUDO service nginx restart

### Setup Supervisor to Start Apps on Boot / Restart on Failures
banner "Configuring Supervisord..."

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
# NOTE: If you used a different directory for the installation then make sure you edit the *.conf files appropriately
cd /usr/local/bin/irrigator/auto-install/supervisor

log_command $SUDO cp *.conf /etc/supervisor/conf.d/

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
log_command $SUDO service supervisor start

# Setup CRONTAB
cd /usr/local/bin/irrigator
log_command $SUDO /usr/local/bin/irrigator/.venv/bin/python initcron.py

# Rebooting
whiptail --msgbox --backtitle "Install Complete / Reboot Required" --title "Installation Completed - Rebooting" "Congratulations, the installation is complete.  At this time, we will perform a reboot and your application should be ready.  You should be able to access your application by opening a browser on your PC or other device and using the IP address for this SBC.  Enjoy!" ${r} ${c}
log_note "Rebooting now."
log_command $SUDO reboot
