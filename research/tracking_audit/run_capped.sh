#!/bin/bash
# Run a command under a memory and wall-clock cap on the shared server.
#
#   run_capped.sh CAP_GB TIMEOUT_S LOG -- cmd args...
#
# The command runs in its own process group. A watchdog sums the RSS of that group every
# 2 s and kills only that group when it exceeds CAP_GB or runs longer than TIMEOUT_S.
# Each process is also limited by `ulimit -v CAP_GB` unless NO_VLIMIT=1 (CUDA reserves a
# large virtual address space). Exits with the command's status, or 137 if the watchdog
# killed it, and appends a "[watchdog] done rc=..." line to LOG.
set -u
CAP_GB=$1; LIMIT_S=$2; LOG=$3; shift 4
CAP_KB=$(( CAP_GB * 1024 * 1024 ))
[ -z "${NO_VLIMIT:-}" ] && ulimit -v "$CAP_KB"

setsid "$@" > "$LOG" 2>&1 &
PID=$!
sleep 1
PGID=$(ps -o pgid= -p "$PID" | tr -d ' ')
START=$(date +%s); PEAK=0; KILLED=0
while kill -0 "$PID" 2>/dev/null; do
  RSS_KB=$(ps -o rss= -g "$PGID" 2>/dev/null | awk '{s+=$1} END {print s+0}')
  [ "$RSS_KB" -gt "$PEAK" ] && PEAK=$RSS_KB
  ELAPSED=$(( $(date +%s) - START ))
  if [ "$RSS_KB" -gt "$CAP_KB" ] || [ "$ELAPSED" -gt "$LIMIT_S" ]; then
    echo "[watchdog] killing pgid $PGID rss_kb=$RSS_KB elapsed=${ELAPSED}s" >> "$LOG"
    kill -9 -- -"$PGID"
    KILLED=1
    break
  fi
  sleep 2
done
wait "$PID" 2>/dev/null
RC=$?
[ "$KILLED" = 1 ] && RC=137
echo "[watchdog] done rc=$RC peak_group_rss_GB=$(awk "BEGIN{print $PEAK/1048576}") elapsed=$(( $(date +%s) - START ))s" >> "$LOG"
exit "$RC"
