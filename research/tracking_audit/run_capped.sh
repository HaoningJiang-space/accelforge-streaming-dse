#!/bin/bash
# Run a command under a memory and wall-clock cap on the shared server.
#
#   run_capped.sh CAP_GB TIMEOUT_S LOG -- cmd args...
#
# The command runs in its own process group. A watchdog sums the RSS of that group every
# 2 s and kills the whole group when it exceeds CAP_GB or runs longer than TIMEOUT_S.
# Each process is also limited by `ulimit -v CAP_GB` unless NO_VLIMIT=1 (CUDA reserves a
# large virtual address space).
#
# Exit status: the command's status; 137 if the watchdog killed the group; 4 if the
# command exited but left processes in its group, which are then killed after a 5 s grace.
# A "[watchdog] done rc=..." line is appended to LOG in every case.
#
# Limits: sampling every 2 s can miss a short spike, and processes that leave the group
# (setsid) escape the watchdog. Use a cgroup when a hard tree-wide limit is required.
set -u
CAP_GB=$1; LIMIT_S=$2; LOG=$3; shift 4
CAP_KB=$(( CAP_GB * 1024 * 1024 ))
[ "${NO_VLIMIT:-0}" = 1 ] || ulimit -v "$CAP_KB"

setsid "$@" > "$LOG" 2>&1 &
PID=$!
PGID=$PID  # setsid makes the child a group leader
START=$(date +%s); PEAK=0; KILLED=0; MAIN_RC=
group_alive() { [ -n "$(ps -o pid= -g "$PGID" 2>/dev/null)" ]; }

while group_alive; do
  RSS_KB=$(ps -o rss= -g "$PGID" 2>/dev/null | awk '{s+=$1} END {print s+0}')
  [ "$RSS_KB" -gt "$PEAK" ] && PEAK=$RSS_KB
  ELAPSED=$(( $(date +%s) - START ))
  if [ "$RSS_KB" -gt "$CAP_KB" ] || [ "$ELAPSED" -gt "$LIMIT_S" ]; then
    echo "[watchdog] killing pgid $PGID rss_kb=$RSS_KB elapsed=${ELAPSED}s" >> "$LOG"
    kill -9 -- -"$PGID" 2>/dev/null
    KILLED=1
    break
  fi
  if [ -z "$MAIN_RC" ] && ! kill -0 "$PID" 2>/dev/null; then
    wait "$PID" 2>/dev/null; MAIN_RC=$?
    MAIN_EXIT=$(date +%s)
  fi
  if [ -n "$MAIN_RC" ] && [ $(( $(date +%s) - MAIN_EXIT )) -ge 5 ]; then
    echo "[watchdog] command exited but left processes in pgid $PGID; killing them" >> "$LOG"
    kill -9 -- -"$PGID" 2>/dev/null
    KILLED=2
    break
  fi
  sleep 2
done
if [ -z "$MAIN_RC" ]; then
  wait "$PID" 2>/dev/null; MAIN_RC=$?
fi
case $KILLED in
  1) RC=137 ;;
  2) RC=4 ;;
  *) RC=$MAIN_RC ;;
esac
echo "[watchdog] done rc=$RC peak_group_rss_GB=$(awk "BEGIN{print $PEAK/1048576}") elapsed=$(( $(date +%s) - START ))s" >> "$LOG"
exit "$RC"
