#!/bin/bash
set -e

PI="pellenz@192.168.178.158"
REMOTE_DIR="/home/pellenz/proj/roboclock"

echo "==> Syncing files to Pi..."
rsync -avz \
  --exclude '.git' \
  --exclude '.idea' \
  --exclude '.vscode' \
  --exclude 'venv' \
  --exclude 'venvnsource' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  /Users/pellenz/proj/roboclock/ \
  "$PI:$REMOTE_DIR/"

echo "==> Restarting roboclock on Pi..."
ssh "$PI" bash <<'ENDSSH'
  # Kill any existing roboclock process
  pkill -f "python3.*roboclock.py" 2>/dev/null || true
  sleep 1
  # Kill existing screen session if present
  screen -S roboclock -X quit 2>/dev/null || true
  # Start roboclock in a detached screen session
  cd /home/pellenz/proj/roboclock
  screen -dmS roboclock bash -c "source venv/bin/activate && python3 ./roboclock.py current.csv"
  sleep 1
  screen -ls
  echo "roboclock restarted."
ENDSSH

echo "==> Done!"
