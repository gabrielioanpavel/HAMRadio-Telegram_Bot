#!/bin/bash

set -e

log() {
  echo "[INFO] $1"
}

log "Updating system..."
sudo apt update
sudo apt upgrade

log "Installing dependencies: wget, unzip..."
sudo apt-get install -y wget unzip

log "Downloading Google Chrome..."
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

log "Installing Google Chrome..."
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb

log "Cleaning up Chrome .deb file..."
rm google-chrome-stable_current_amd64.deb

CHROME_VERSION=$(google-chrome --version | grep -oP "\d+\.\d+\.\d+")
log "Installed Chrome version: $CHROME_VERSION"