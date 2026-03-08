#!/bin/bash
set -e

PI="pellenz@192.168.178.158"

echo "==> Restarting roboclock on Pi..."
ssh "$PI" bash <<'ENDSSH'
  pkill -f "python3.*roboclock.py" 2>/dev/null || true
  sleep 1
  screen -S roboclock -X quit 2>/dev/null || true
  cd /home/pellenz/proj/roboclock
  screen -dmS roboclock bash -c "source venv/bin/activate && python3 ./roboclock.py current.csv"
  sleep 1
  screen -ls
  echo "roboclock restarted."
ENDSSH

echo "==> Done!"
