#!/bin/sh
SRC=$(pwd)
cd ~/ohr/rpgbatch
python3 $SRC/process_rpgs.py src:bahamut /home/teeemcee/web/ohr/archive/Bahamut/games/ src:ohrhits ohrhits src:opohr  /home/castleparadox/web/archive/operationohr/gamelist/* src:opohr-extra /home/castleparadox/web/archive/operationohr/ src:cp /home/castleparadox/web/gamelist/* src:extra moregames src:aeth /home/castleparadox/web/aeth/ src:ss slimesalad/*

#src:mezase_master nintendork
