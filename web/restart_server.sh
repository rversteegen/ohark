#!/bin/sh

./stop_server.sh
nohup ./local_server.py &
sleep 0.2
