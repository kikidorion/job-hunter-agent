#!/bin/bash
# Installs a launchd job that runs the agent at 7:00 and 16:00 every day (edit HOURS to change).
# Undo: launchctl unload ~/Library/LaunchAgents/com.jobhunter.agent.plist && rm that file
set -e
HOURS="7 16"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.jobhunter.agent.plist"
times=""
for h in $HOURS; do times="$times<dict><key>Hour</key><integer>$h</integer><key>Minute</key><integer>0</integer></dict>"; done
mkdir -p "$REPO/logs" "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.jobhunter.agent</string>
  <key>ProgramArguments</key><array><string>$REPO/scripts/run.sh</string></array>
  <key>StartCalendarInterval</key><array>$times</array>
  <key>StandardErrorPath</key><string>$REPO/logs/launchd.err</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Scheduled at hours: $HOURS. Logs: $REPO/logs/scheduler.log"
