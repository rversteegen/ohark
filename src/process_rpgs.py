#!/usr/bin/env python
"""
This module builds a DB by scanning .zip files.
It depends on nohrio (rpgbatch fork) and rpgbatch which need to be in the path.
See http://rpg.hamsterrepublic.com/ohrrpgce/nohrio
and tools/rpgbatch/rpgbatch.py in the OHRRPGCE repository.
(http://rpg.hamsterrepublic.com/source/tools/rpgbatch/rpgbatch.py)
"""
from __future__ import print_function
import os
import sys
import time
import random
import numpy as np
import localsite
import nohrio.ohrrpgce
from rpgbatch import RPGIterator, RPGInfo, ArchiveInfo
import scrape
from gamedb import BinData

import gamedb

def process_sources(db_name, sources):
    """
    Create and write a GameList.
    sources is a list of .rpg files, .rpgdir directories, .zip files, or directories containing any of these.
    """
    games_db = gamedb.GameList(db_name)
    zips_db = {}

    # Ask the iterator to yield both each game it finds, and each zip file it processes
    iterator = RPGIterator(sources, yield_zips = True)
    for yielded in iterator:
        if isinstance(yielded, ArchiveInfo):
            # A zip file
            zipinfo = yielded
            srcid = "%d" % random.randint(0,1000)  # Placeholder to avoid collisions (TODO)
            zipkey = (zipinfo.src, srcid, os.path.split(zipinfo.path)[1])
            print("Processing ZIP", zipkey)
            assert zipkey not in zips_db   # Shouldn't happen!

            zipdata = gamedb.ScannedZipData(zipinfo)
            zips_db[zipkey] = zipdata
            if zipdata.unreadable:
                continue   # We didn't read any games from this zip

            # Now that we've added this zip to the DB,
            # point every game in it to the DB entry for this zip file.
            for fname, gameid in zipdata.rpgs.items():
                # If the game was corrupt, then it didn't get added to the DB
                if gameid in games_db.games:
                    games_db.games[gameid].archives.append(zipkey)
            continue

        rpg, gameinfo, zipinfo = yielded
        gameid = gameinfo.hash[:9]

        # The filenames of .zips from Op:OHR contain URL %xx escape codes, need to remove
        # to get a gameid that can be part of a valid URL.
        #... however, this string is no longer used for anything
        #verbose_game_id = (gameinfo.src + ': ' + scrape.unquote(gameinfo.id).replace('/', '-')).lower().decode('latin-1')

        print("Processing RPG ", gameinfo.id, "from", gameinfo.src)
        print(" > ", gameinfo.longname, " --- ", gameinfo.aboutline)

        game = gamedb.Game()
        game.src = gameinfo.src
        game.name = (gameinfo.longname or gameinfo.rpgfile).decode('latin-1').strip()
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
                game.fixbits = BinData(f.read())
            fixBits = nohrio.ohrrpgce.fixBits(rpg.lump_path('fixbits.bin'))
        else:
            game.fixbits = None
            fixBits = None

        if not fixBits or not fixBits.wipegen:
            # In old .rpg files, gen contains garbage; this fixbit indicates if it's been cleaned
            gen[199:] = 0
        game.gen = BinData(gen.tostring())
            
        info = [
            "Filename: " + gameinfo.rpgfile,
            "Size: %d KB" % (game.size / 1024),
            "md5: " + gameinfo.hash,
            "Created by: " + rpg.archinym.version,
            "archinym: " + rpg.archinym.prefix,
        ]
        # if zipinfo and len(zipinfo.scripts):
        #     info.append("Script files: " + str(zipinfo.scripts))
        game.extra_info = "\n".join(info)

        # Double-check that there are no undecoded strings
        game = scrape.clean_strings(game)

        games_db.games[gameid] = game

    iterator.print_summary()

    games_db.save()
    gamedb.DataBaseLayer.save('zips', zips_db)

if len(sys.argv) < 2:
    sys.exit("Specify .rpg files, .rpgdir directories, .zip files, or directories containing any of these as arguments.")
sources = sys.argv[1:]
process_sources("rpgs", sources)
