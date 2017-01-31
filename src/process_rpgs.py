#!/usr/bin/env python
"""
This module builds a DB by scanning .zip files.
It depends on nohrio (rpgbatch fork) and rpgbatch which need to be in the path.
See http://rpg.hamsterrepublic.com/ohrrpgce/nohrio
and tools/rpgbatch/rpgbatch.py in the OHRRPGCE repository.
(https://rpg.hamsterrepublic.com/source/tools/rpgbatch/rpgbatch.py)
"""
import os
import sys
import time
import numpy as np
import localsite
from nohrio.ohrrpgce import *
from rpgbatch import RPGIterator, RPGInfo
from rpg_const import *

import gamedb

def process_sources(db_name, sources):
    """
    Create and write a GameList.
    sources is a list of .rpg files, .rpgdir directories, .zip files, or directories containing any of these.
    """
    db = gamedb.GameList(db_name)

    rpgs = RPGIterator(sources)
    for rpg, gameinfo, zipinfo in rpgs:
        #lumplist = [(lumpbasename(name, rpg), os.stat(name).st_size) for name in rpg.manifest]
        gameid = (gameinfo.src + ': ' + gameinfo.id.replace('/', '-')).lower()

        print "Processing RPG ", gameinfo.id, "as", gameid
        print " > ", gameinfo.longname, " --- ", gameinfo.aboutline

        game = gamedb.Game()
        game.name = gameinfo.longname.decode('latin-1')
        game.description = gameinfo.aboutline.decode('latin-1')

        if gameinfo.rpgfile.lower().endswith('.rpgdir'):
            size = sum(os.stat(name).st_size for name in rpg.manifest)
        else:
            size = gameinfo.size

        # Get info
        gen = rpg.general.view(np.int16)
        info = [
            "Filename: " + gameinfo.rpgfile,
            "Size: %d KB" % (size / 1024),
            ".rpg version: %d" % gen[genVersion],
            "Num maps: %d" % (gen[genMaxMap] + 1),
            "Num textboxes: %d" % (gen[genMaxTextbox] + 1),
            "Num formations: %d" % (gen[genMaxFormation] + 1),
            "Num backdrops: %d" % gen[genNumBackdrops],
            "Num scripts: %d" % gen[genNumPlotscripts],
            "Num songs: %d" % (gen[genMaxSong] + 1),
            "Battle mode: %s" % ({0:"Active-battle", 1:"Turn-based"}.get(gen[genBattleMode], "UNKNOWN!")),
            "Resolution: %dx%d" % (gen[genResolutionX] or 320, gen[genResolutionY] or 200),
            "Frame rate: %.1fFPS" % (1000. / (gen[genMillisecPerFrame] or 55)),
            "Created by: " + rpg.archinym.version,
            "archinym: " + rpg.archinym.prefix,
        ]
        if zipinfo and len(zipinfo.scripts):
            info.append("Script files: " + str(zipinfo.scripts))
        game.extra_info = "<br/>".join(info)
        game.mtime = gameinfo.mtime

        db.games[gameid] = game

    rpgs.print_summary()
    del rpgs

    db.save()


if len(sys.argv) < 2:
    sys.exit("Specify .rpg files, .rpgdir directories, .zip files, or directories containing any of these as arguments.")
sources = sys.argv[1:]
process_sources("rpgs", sources)
