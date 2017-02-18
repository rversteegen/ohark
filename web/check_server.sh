#!/bin/sh

PSINFO=$(ps aux|grep local_server.py | grep -v grep)
PID=$(echo $PSINFO | cut -d ' ' -f2)
if [ -n "$PID" ]; then
    ps u --pid $PID
else
    echo "Not running!"
fi
