#!/bin/bash
# Scheduler entry point (launchd / cron). Runs from the repo folder, waits for the network after
# wake, and holds a lock so a slow run never overlaps the next one.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs data
for _ in $(seq 1 36); do   # after sleep, schedulers fire before Wi-Fi is back: wait up to 3 min
  curl -s -o /dev/null --max-time 3 https://api.typesafe.ai && break
  sleep 5
done
PY=./.venv/bin/python
if command -v flock >/dev/null; then          # Linux
  exec flock -n data/.run.lock "$PY" -m jobhunt run >> logs/scheduler.log 2>&1
elif command -v lockf >/dev/null; then        # macOS
  exec lockf -t 0 data/.run.lock "$PY" -m jobhunt run >> logs/scheduler.log 2>&1
else
  exec "$PY" -m jobhunt run >> logs/scheduler.log 2>&1
fi
