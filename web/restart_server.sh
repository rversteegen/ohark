#!/bin/sh

./stop_server.sh
echo :starting: $(date) >> process_log.txt
nohup ./local_server.py &
sleep 0.2
