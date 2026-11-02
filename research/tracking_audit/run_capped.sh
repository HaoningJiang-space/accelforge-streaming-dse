#!/bin/bash
# Usage: run_capped.sh <total_rss_GB> <timeout_s> <log> -- cmd args...
# Runs cmd in its own process group; kills only that group if total RSS or time exceeds the cap.
CAP_GB=$1; LIMIT_S=$2; LOG=$3; shift 4
# CUDA reserves huge virtual address space, so GPU runs set NO_VLIMIT=1 and rely on the RSS watchdog
[ -z "$NO_VLIMIT" ] && ulimit -v $(( CAP_GB * 1024 * 1024 ))
setsid "$@" > "$LOG" 2>&1 &
PID=$!
sleep 1
PGID=$(ps -o pgid= -p $PID | tr -d ' ')
START=$(date +%s); PEAK=0
while kill -0 $PID 2>/dev/null; do
  RSS_KB=$(ps -o rss= -g "$PGID" 2>/dev/null | awk '{s+=$1} END {print s+0}')
  [ "$RSS_KB" -gt "$PEAK" ] && PEAK=$RSS_KB
  NOW=$(date +%s)
  if [ "$RSS_KB" -gt $(( CAP_GB * 1024 * 1024 )) ] || [ $(( NOW - START )) -gt "$LIMIT_S" ]; then
    echo "[watchdog] killing pgid $PGID rss_kb=$RSS_KB elapsed=$(( NOW - START ))" >> "$LOG"
    kill -9 -- -"$PGID"
    break
  fi
  sleep 2
done
wait $PID 2>/dev/null
echo "[watchdog] done rc=$? peak_group_rss_GB=$(awk "BEGIN{print $PEAK/1048576}") elapsed=$(( $(date +%s) - START ))s" >> "$LOG"
