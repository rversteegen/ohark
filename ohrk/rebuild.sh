#!/bin/sh

./pull_castleparadox.py  &
./pull_castleparadox.py --backup &
./pull_google_play.py &
./pull_opohr_from_backup.py &
./pull_slimesalad.py &
./pull_hamsterspeak.py &
./pull_pepsi.py &

wait $(jobs -p)
