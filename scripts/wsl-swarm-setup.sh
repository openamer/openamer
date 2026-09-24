#!/bin/bash
# OpenAmer WSL Swarm-Node Setup
# Führt nach apt-Install aus: richtet den WSL-Node für den OpenAmer-Swarm ein

set -e

echo "=== OpenAmer Swarm-Node Setup ==="

# Python-Tools
pip3 install --user --quiet requests psutil 2>/dev/null

# Git-Config
git config --global user.name "OpenAmer WSL"
git config --global user.email "openamer@wsl.local"

# OpenAmer Home einbinden (vom Windows-Host)
OPENAMER_HOME="/mnt/c/Users/damir/AppData/Local/openamer-laptop"

# Symlink für schnellen Zugriff
ln -sf "$OPENAMER_HOME" ~/openamer-home

# SSH-Key für GPU-Worker (wenn vorhanden)
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -q
    echo "SSH-Key generiert: $(cat ~/.ssh/id_rsa.pub)"
fi

# Swarm-Node identifizieren
echo "Hostname: $(hostname)"
echo "OpenAmer Home: $OPENAMER_HOME"
echo "Python: $(python3 --version)"
echo "Node ready for swarm."