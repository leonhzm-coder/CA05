#!/bin/sh
# CA05 - Cross-Cloud Operations Assistant
# This script installs dependencies and starts the server

echo "=== Installing dependencies ==="
python3 -m pip install -r requirements.txt -q
echo "=== Starting CA05 Server ==="
exec python3 main.py
