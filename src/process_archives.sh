#!/bin/sh
# Builds the 'rpgs' DB by scanning lots of archives. Archives not included.

SRC=$(pwd)
# Don't cd, as data/ directory is created here
#cd ~/ohr/archive

# (Note to self) see
#  fd . -e 'rpg' -e zip -e rar -e gz ~/ohr/archive/ |sort> ~/ohr/archive/rpgfiles.txt
# for more, and also backup/web/

ARCHIVE=~/ohr/archive

python3 $SRC/process_rpgs.py src:ss $ARCHIVE/slimesalad/* src:cp $ARCHIVE/cp_gamelist/*/ src:opohr  $ARCHIVE/operationohr/gamelist/* src:opohr-extra $ARCHIVE/operationohr/ src:extra $ARCHIVE/moregames/ $ARCHIVE/extra_games/ src:ohrhits $ARCHIVE/ohrhits/*.zip src:ohrsrc $ARCHIVE/ohrrpgce-source-2000.zip $ARCHIVE/ohr_src_2003 src:bahamut $ARCHIVE/Bahamut/ $ARCHIVE/Bahamut/www.angelfire.com/scifi/jm11/games/*.zip src:unreleased ~/ohr/games/unreleased/* ~/ohr/tests/

#src:mezase_master nintendork
