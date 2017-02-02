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
import scrape

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
        # The filenames of .zips from Op:OHR contain URL %xx escape codes, need to remove
        # to get a gameid that can be part of a valid URL.
        gameid = (gameinfo.src + ': ' + scrape.unquote(gameinfo.id).replace('/', '-')).lower()

        print "Processing RPG ", gameinfo.id, "as", gameid
        print " > ", gameinfo.longname, " --- ", gameinfo.aboutline

        game = gamedb.Game()
        game.name = gameinfo.longname
        if not game.name:
            game.name = gameinfo.rpgfile
        game.name = game.name.decode('latin-1')
        game.description = gameinfo.aboutline.decode('latin-1')

        if gameinfo.rpgfile.lower().endswith('.rpgdir'):
            game.size = sum(os.stat(name).st_size for name in rpg.manifest)
        else:
            game.size = gameinfo.size
        game.mtime = gameinfo.mtime

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
        game.gen = gen.tostring()
            
        info = [
            "Filename: " + gameinfo.rpgfile,
            "Size: %d KB" % (game.size / 1024),
            "Created by: " + rpg.archinym.version,
            "archinym: " + rpg.archinym.prefix,
        ]
        if zipinfo and len(zipinfo.scripts):
            info.append("Script files: " + str(zipinfo.scripts))
        game.extra_info = "\n".join(info)

        db.games[gameid] = game

    rpgs.print_summary()

    db.save()


if len(sys.argv) < 2:
    sys.exit("Specify .rpg files, .rpgdir directories, .zip files, or directories containing any of these as arguments.")
sources = sys.argv[1:]
process_sources("rpgs", sources)
