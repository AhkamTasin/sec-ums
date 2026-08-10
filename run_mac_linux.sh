#!/bin/bash
# =====================================================================
#  University Management System - one-command runner for macOS/Linux
#  Usage:  bash run_mac_linux.sh
# =====================================================================
cd "$(dirname "$0")"

echo "--------------------------------------"
echo " Installing Django & libraries (needs internet once)"
echo "--------------------------------------"
python3 -m pip install -r requirements.txt || { echo; echo "[ERROR] Python 3 not found. Install it from https://www.python.org/downloads/"; exit 1; }

echo
echo "--------------------------------------"
echo " Preparing the database"
echo "--------------------------------------"
python3 manage.py migrate
python3 manage.py seed_demo

echo
echo "--------------------------------------"
echo " Starting the server..."
echo " Open this address in your browser:"
echo
echo "      http://127.0.0.1:8000"
echo
echo " Press Ctrl+C to stop the server."
echo "--------------------------------------"
python3 manage.py runserver
