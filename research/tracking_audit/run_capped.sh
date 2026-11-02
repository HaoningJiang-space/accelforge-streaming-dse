#!/bin/bash
# Usage: run_capped.sh CAP_GB TIMEOUT_S LOG -- cmd args...
# Standard-library Python supervises startup, PGID selection, and signal cleanup.
# NO_VLIMIT=1 disables only the per-process virtual-memory limit, not RSS/timeout.
# Exit: child status; 137 for budget exhaustion; 4 for orphaned group members;
# 128+signal for supervisor cancellation; 125 for setup/monitoring failure.
exec python3 "$(dirname -- "$0")/run_capped.py" "$@"
