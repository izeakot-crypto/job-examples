#!/bin/bash
# Indeed Peru Parser - Run Script
# Schedule: Wednesday 12:00

cd /home/vibe_user/indeed_pe
source venv/bin/activate

# Log file with timestamp
LOG_FILE="cron_output_$(date +%Y%m%d_%H%M%S).log"

echo "Starting Indeed Peru Parser at $(date)" >> "$LOG_FILE"
xvfb-run -a python3 project.py >> "$LOG_FILE" 2>&1
echo "Finished at $(date)" >> "$LOG_FILE"
