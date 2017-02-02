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
import nohrio.ohrrpgce
from rpgbatch import RPGIterator, RPGInfo
from rpg_const import *
import scrape

import gamedb

# Description of each genVersion value
rpg_version_info = {
    0: "1998 Super-ancient format",
    1: "1998 ancient format",
    2: "1999-06-18",
    3: "1999-07-08",
    4: "2000-09-15",
    5: "2001-03-31",
    6: "2006-02-13 serendipity", # MIDI music, shop stuff
    7: "2008-11-21 ypsiliform", # wip added > 36 NPC defs (and many other features)
    8: "2009-09-23 ypsiliform", # wip added extended chaining data (and many other features)
    9: "2009-10-20 ypsiliform", # wip added text box sound effects
    10: "2009-12-11 ypsiliform", # wip added attack-based enemy transmogrification
    11: "2010-07-28 zenzizenzic", # wip added variable record size and record number .N## lumps
    12: "2010-10-20 zenzizenzic", # wip increased .N## record size
    13: "2010-12-30 zenzizenzic", # wip changed password format to PW4, older versions have broken genPassVersion handling
    14: "2011-01-05 zenzizenzic", # wip made .DT0 binsize-sized
    15: "2011-01-20 zenzizenzic", # wip made .DT1 binsize-sized, and added binsize.bin, fixbits.bit safeguards
    16: "2011-01-20 zenzizenzic", # wip made .ITM binsize-sized
    17: "2012-02-08 alectormancy", # wip increase global limit from 4095 to 16383
    18: "2012-12-06 beelzebufo", # turn-based support
    19: "2012-12-21 beelzebufo", # replaced .dt0 with heroes.reld
    19: "2012-12-21 beelzebufo", # replaced .DT0 with heroes.reld
    20: "2016-03-19 callipygous", # release. Added general.reld (including new version system) and maxScriptCmdID checking.
}

def process_sources(db_name, sources):
    """
    Create and write a GameList.
    sources is a list of .rpg files, .rpgdir directories, .zip files, or directories containing any of these.
    """
    db = gamedb.GameList(db_name)

    rpgs = RPGIterator(sources)
    for rpg, gameinfo, zipinfo in rpgs:
        #lumplist = [(lumpbasename(name, rpg), os.stat(name).st_size) for name in rpg.manifest]
        # The filenames of .zips from Op:OHR contain URL %xx escape codes, need to remove
        # to get a gameid that can be part of a valid URL.
        gameid = (gameinfo.src + ': ' + scrape.unquote(gameinfo.id).replace('/', '-')).lower()

        print "Processing RPG ", gameinfo.id, "as", gameid
        print " > ", gameinfo.longname, " --- ", gameinfo.aboutline

        game = gamedb.Game()
        game.name = gameinfo.longname.decode('latin-1')
        if not game.name:
            game.name = gameinfo.rpgfile
        game.description = gameinfo.aboutline.decode('latin-1')

        if gameinfo.rpgfile.lower().endswith('.rpgdir'):
            size = sum(os.stat(name).st_size for name in rpg.manifest)
        else:
            size = gameinfo.size

        # Read some data out of the .rpg file, including .gen and fixbits lumps,
        # and put some info into 

        gen = rpg.general.view(np.int16).copy()

        if rpg.has_lump('fixbits.bin'):
            with open(rpg.lump_path('fixbits.bin')) as f:
                game.fixbits = f.read()
            fixBits = nohrio.ohrrpgce.fixBits(rpg.lump_path('fixbits.bin'))
        else:
            game.fixbits = None
            fixBits = None

        if not fixBits or not fixBits.wipegen:
            # In old .rpg files, gen contains garbage; this fixbit indicates if it's been cleaned
            gen[199:] = 0
            print len(gen)

        battle_mode = ({0:"Active-battle", 1:"Turn-based"}
                       .get(gen[genBattleMode], "UNKNOWN! (%d)" % gen[genBattleMode]))
        version_info = rpg_version_info.get(gen[genVersion], "Unknown!")
        if gen[genVersion] + 1 in rpg_version_info:
            # Add the date of the next version
            version_info += ", until " + rpg_version_info[gen[genVersion] + 1].split()[0]
            
        info = [
            "Filename: " + gameinfo.rpgfile,
            "Size: %d KB" % (size / 1024),
            ".rpg version: %d (%s)" % (gen[genVersion], version_info),
            "Num maps: %d" % (gen[genMaxMap] + 1),
            "Num textboxes: %d" % (gen[genMaxTextbox] + 1),
            "Num formations: %d" % (gen[genMaxFormation] + 1),
            "Num enemies: %d" % (gen[genMaxEnemy] + 1),
            "Num backdrops: %d" % gen[genNumBackdrops],
            "Num tilesets: %d" % (gen[genMaxTile] + 1),
            "Num scripts: %d" % gen[genNumPlotscripts],
            "Num songs: %d" % (gen[genMaxSong] + 1),
            "Num sound effects: %d" % (gen[genMaxSFX] + 1),
            "Battle mode: " + battle_mode,
            "Resolution: %dx%d" % (gen[genResolutionX] or 320, gen[genResolutionY] or 200),
            "Frame rate: %.1fFPS" % (1000. / (gen[genMillisecPerFrame] or 55)),
            "Created by: " + rpg.archinym.version,
            "archinym: " + rpg.archinym.prefix,
        ]
        game.gen = gen.tostring()

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
