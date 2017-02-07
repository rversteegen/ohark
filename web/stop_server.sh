#!/bin/sh

PSINFO=$(ps aux|grep local_server.py | grep -v grep)
PID=$(echo $PSINFO | cut -d ' ' -f2)
if [ -n "$PID" ]; then
    echo "Killing::"
    ps u --pid $PID
    kill $PID
else
    echo "Not running!"
fi
